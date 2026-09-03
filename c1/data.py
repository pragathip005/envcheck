"""Download and locally cache HardTests problems.

Streams `sigcp/hardtests_problems` from HuggingFace rather than
`load_dataset(..., streaming=False)`, which would try to materialize the
whole (large) dataset before we've even picked a subset. Caches to JSONL so
repeat runs don't re-hit the network.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PROBLEMS_CACHE = DATA_DIR / "problems_sample.jsonl"


def fetch_problems(limit: int, cache_path: Path = PROBLEMS_CACHE) -> list[dict]:
    """Return the first `limit` rows of sigcp/hardtests_problems, caching to disk.

    Not a random or difficulty-filtered sample - just the dataset's own row
    order, truncated. Good enough to build and test verifiers against; picking
    the actual 100 pilot problems (plan.md §2's 20-70% pass@8 learnable band)
    is a separate step that needs real model rollouts, not just this data.
    """
    if cache_path.exists():
        rows = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines()]
        if len(rows) >= limit:
            return rows[:limit]

    from datasets import load_dataset

    ds = load_dataset("sigcp/hardtests_problems", split="train", streaming=True)
    rows = []
    for row in ds:
        rows.append(row)
        if len(rows) >= limit:
            break

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return rows


def python_solution(problem: dict) -> str | None:
    """First solution actually written in Python, ignoring the `language`
    field - it's unreliable (seen at least one solution tagged "cpp" whose
    `code` was plainly Python). Falls back to sniffing content instead.
    """
    for sol in problem.get("solutions", []):
        code = sol.get("code", "")
        looks_python = "def " in code or "input()" in code or code.strip().startswith("python")
        looks_cpp = "#include" in code or "using namespace" in code
        if looks_python and not looks_cpp:
            return code.removeprefix("python\n") if code.startswith("python\n") else code
    return None
