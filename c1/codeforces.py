"""Codeforces-only C1 pilot pool: join sigcp/hardtests_problems (V0 material)
to deepmind/code_contests (V1 material) by contest_id/index parsed from the
problem URL.

Restricted to Codeforces because it's the one platform where a real,
distinct "original tests" (V1) exists separately from HardTests' own public
tests (V0) - see docs/LEARNING_LOG.md's "V1 isn't a free lookup" entry for
why AtCoder/Luogu/TACO-routed problems don't have this. Confirmed by the user
as the deliberate scope for the pilot pool, not an accident of convenience.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
POOL_CACHE = DATA_DIR / "codeforces_pool.jsonl"

_URL_RE = re.compile(r"codeforces\.com/problemset/problem/(\d+)/([A-Za-z0-9]+)")


def _parse_cf_url(url: str) -> tuple[int, str] | None:
    m = _URL_RE.search(url or "")
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def fetch_codeforces_hardtests(target_count: int, scan_limit: int = 20000) -> list[dict]:
    """Stream sigcp/hardtests_problems, keeping only platform == "codeforces"
    rows with a parseable URL, until target_count are collected or scan_limit
    rows have been scanned (the dataset isn't shuffled and isn't evenly mixed
    by platform shard-to-shard, so this is a real scan, not an index lookup).
    """
    from datasets import load_dataset

    ds = load_dataset("sigcp/hardtests_problems", split="train", streaming=True)
    found = []
    scanned = 0
    for row in ds:
        scanned += 1
        if row["platform"] == "codeforces":
            parsed = _parse_cf_url(row["url"])
            if parsed is not None:
                row["_cf_contest_id"], row["_cf_index"] = parsed
                found.append(row)
                if len(found) >= target_count:
                    break
        if scanned >= scan_limit:
            break
    return found


def join_code_contests(
    hardtests_rows: list[dict], scan_limit_per_split: int = 200000
) -> dict[tuple[int, str], dict]:
    """Stream deepmind/code_contests (train + valid + test splits) looking for
    rows matching the (cf_contest_id, cf_index) pairs in hardtests_rows.
    Stops each split early once every target has been found. Returns a dict
    keyed by (contest_id, index).
    """
    from datasets import load_dataset

    targets = {(r["_cf_contest_id"], r["_cf_index"]) for r in hardtests_rows}
    matches: dict[tuple[int, str], dict] = {}

    for split in ("train", "valid", "test"):
        if len(matches) >= len(targets):
            break
        ds = load_dataset("deepmind/code_contests", split=split, streaming=True)
        scanned = 0
        for row in ds:
            scanned += 1
            key = (row.get("cf_contest_id"), row.get("cf_index"))
            if key in targets and key not in matches:
                matches[key] = row
                if len(matches) >= len(targets):
                    break
            if scanned >= scan_limit_per_split:
                break

    return matches


# deepmind/code_contests' `solutions.language` enum, confirmed empirically
# (not from memory) by checking real code against each integer value present
# in the data: 1 -> genuinely Python-shaped code but old-style (no confirmed
# Python 2 vs 3 split observed), 2 -> C++ (#include/using namespace), 3 ->
# clean Python 3 (input()-based), 4 -> Java. Earlier naive content-sniffing
# ("print(" in code) picked a Java solution here because `pw.print(x)` (a
# PrintWriter call) matches that substring too - use the language field
# directly instead of sniffing content.
CODE_CONTESTS_PYTHON3 = 3


def find_python3_solution(codecontests_row: dict) -> str | None:
    for lang, code in zip(
        codecontests_row["solutions"]["language"], codecontests_row["solutions"]["solution"]
    ):
        if lang == CODE_CONTESTS_PYTHON3:
            return code
    return None


def find_validated_python3_solution(
    hardtests_row: dict, codecontests_row: dict, max_candidates: int = 8
) -> str | None:
    """Like find_python3_solution, but doesn't trust the first match blindly.

    Found by hand that `deepmind/code_contests` labeling a solution
    "language == Python 3" doesn't mean it's actually correct - one real
    example had its whole algorithm sitting inside a `\"\"\"...\"\"\"` block,
    live code just printing a hardcoded fallback (docs/LEARNING_LOG.md's
    "Chased the timeout hypothesis" entry). This is the same check
    `envcheck/probes/gold_sanity.py` already does for exactly this reason -
    does the "known-correct" answer actually pass? - applied here before a
    solution gets used as this problem's gold reference. Tries up to
    `max_candidates` Python 3 solutions in order, returns the first that
    scores 1.0 on both V0 and V1, or None if none do within that budget.
    """
    from c1.verifiers import make_v0_grader, make_v1_grader

    v0 = make_v0_grader(hardtests_row)
    v1 = make_v1_grader(codecontests_row)

    tried = 0
    for lang, code in zip(
        codecontests_row["solutions"]["language"], codecontests_row["solutions"]["solution"]
    ):
        if lang != CODE_CONTESTS_PYTHON3:
            continue
        tried += 1
        if tried > max_candidates:
            break
        if v0(code) == 1.0 and v1(code) == 1.0:
            return code
    return None


def build_pool(target_count: int, cache_path: Path = POOL_CACHE) -> list[dict]:
    """Build (or load from cache) the joined Codeforces pilot pool: each entry
    has both the hardtests_problems row (under "hardtests") and its matched
    code_contests row (under "codecontests"), or None for the latter if no
    match was found - callers should filter those out before using V1.

    Unvalidated - includes problems whose only "Python 3" solution is
    actually broken (see find_validated_python3_solution). Prefer
    build_validated_pool for anything that needs a trustworthy gold solution;
    this is kept around for the raw join itself.
    """
    if cache_path.exists():
        rows = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines()]
        if len(rows) >= target_count:
            return rows[:target_count]

    # Over-fetch: not every Codeforces problem in HardTests will match a
    # code_contests row (CodeContests doesn't cover every Codeforces problem).
    hardtests_rows = fetch_codeforces_hardtests(target_count=int(target_count * 1.5) + 20)
    cc_index = join_code_contests(hardtests_rows)

    pool = []
    for row in hardtests_rows:
        key = (row["_cf_contest_id"], row["_cf_index"])
        pool.append({"hardtests": row, "codecontests": cc_index.get(key)})

    matched = [p for p in pool if p["codecontests"] is not None]
    print(f"matched {len(matched)}/{len(pool)} Codeforces problems to code_contests")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        for row in pool:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return pool[:target_count]


VALIDATED_POOL_CACHE = DATA_DIR / "validated_codeforces_pool.jsonl"

# Measured yield from the first real run (docs/LEARNING_LOG.md, 2026-09-03):
# 30/35 problems had *a* Python 3 solution, 24/30 of those validated - about
# 24/35 = 0.69 raw Codeforces problems become one usable pilot problem.
# Overfetch by more than 1/0.69 to leave margin for the yield rate moving
# around at a different scale.
_MEASURED_YIELD_RATE = 0.6


def build_validated_pool(
    target_count: int, cache_path: Path = VALIDATED_POOL_CACHE, max_rounds: int = 3
) -> list[dict]:
    """Like build_pool, but every returned entry additionally has a
    "validated_solution" key - a Python 3 solution confirmed (not assumed) to
    score 1.0 on both V0 and V1, per find_validated_python3_solution. Entries
    without one are dropped, not returned as None - unlike build_pool, every
    row here is directly usable.

    Fetches more than target_count raw candidates up front based on the
    measured yield rate, validates all of them, and - since that estimate is
    a measurement from one run, not a guarantee - re-fetches a bigger batch
    up to max_rounds times if still short.
    """
    if cache_path.exists():
        rows = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines()]
        if len(rows) >= target_count:
            return rows[:target_count]

    from c1.verifiers import make_v0_grader

    overfetch = int(target_count / _MEASURED_YIELD_RATE) + 20
    validated: list[dict] = []
    seen_keys: set[tuple[int, str]] = set()

    for round_num in range(max_rounds):
        hardtests_rows = fetch_codeforces_hardtests(target_count=overfetch)
        cc_index = join_code_contests(hardtests_rows)

        for row in hardtests_rows:
            key = (row["_cf_contest_id"], row["_cf_index"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            cc_row = cc_index.get(key)
            if cc_row is None:
                continue
            sol = find_validated_python3_solution(row, cc_row)
            if sol is None:
                continue
            validated.append({"hardtests": row, "codecontests": cc_row, "validated_solution": sol})
            if len(validated) >= target_count:
                break

        print(
            f"round {round_num + 1}: {len(validated)}/{target_count} validated "
            f"(from {len(seen_keys)} distinct Codeforces problems scanned)"
        )
        if len(validated) >= target_count:
            break
        overfetch *= 2  # yield rate was worse than expected - try harder next round

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        for row in validated:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return validated[:target_count]
