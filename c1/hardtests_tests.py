"""Fetch and decode sigcp/hardtests_tests rows for V2 (plan.md §2:
"HardTests-generated tests, HackGen included").

Two lessons from getting this working (docs/LEARNING_LOG.md has the full
story): the dataset isn't shuffled, so pids for our Codeforces pool cluster
in a handful of shards rather than being spread evenly across all 121 - scan
cheaply (pid column only, via fsspec range-reads) before deciding a shard is
worth fetching. And the full row (including the base64/zlib/pickle-encoded
`test_cases` blob) is too large for fsspec's HTTP range-read caching to
reliably pull for one row - once a shard is confirmed relevant, download the
whole file with huggingface_hub.hf_hub_download (a proper resumable single
download) rather than fighting partial reads.
"""

from __future__ import annotations

import base64
import json
import pickle
import zlib

import fsspec
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download, hf_hub_url

REPO_ID = "sigcp/hardtests_tests"


def decode_testcases(encoded_testcases: str) -> list[dict]:
    """As documented on the dataset's own card - not our own scheme."""
    return json.loads(
        pickle.loads(zlib.decompress(base64.b64decode(encoded_testcases.encode("utf-8"))))
    )


def _list_shards() -> list[str]:
    info = HfApi().dataset_info(REPO_ID)
    return sorted(s.rfilename for s in info.siblings if s.rfilename.endswith(".parquet"))


def fetch_for_pids(target_pids: set[str], max_shards: int | None = None) -> dict[str, dict]:
    """Return {pid: row} for every pid in target_pids found in
    sigcp/hardtests_tests, with row["_decoded_test_cases"] already decoded.
    Stops once every target pid is found or max_shards is exhausted.
    """
    shards = _list_shards()
    if max_shards is not None:
        shards = shards[:max_shards]

    fs = fsspec.filesystem("https")
    found: dict[str, dict] = {}

    for i, shard in enumerate(shards):
        if len(found) >= len(target_pids):
            break
        url = hf_hub_url(REPO_ID, shard, repo_type="dataset")
        with fs.open(url, "rb") as f:
            pqf = pq.ParquetFile(f)
            shard_has_match = False
            for rg in range(pqf.num_row_groups):
                pids_in_group = pqf.read_row_group(rg, columns=["pid"]).column("pid").to_pylist()
                if target_pids.intersection(pids_in_group) - found.keys():
                    shard_has_match = True
                    break

        if not shard_has_match:
            continue

        print(f"shard {i} ({shard}) has matches - downloading full file")
        local_path = hf_hub_download(repo_id=REPO_ID, filename=shard, repo_type="dataset")
        table = pq.read_table(local_path, columns=["pid", "test_cases_kit", "mapping", "test_cases"])
        for row in table.to_pylist():
            if row["pid"] in target_pids and row["pid"] not in found:
                row["_decoded_test_cases"] = decode_testcases(row["test_cases"])
                found[row["pid"]] = row

    return found
