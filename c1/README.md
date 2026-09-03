# C1 pilot prep

Data and verifier prep for plan.md's C1 experiment (§2) — not part of the
`envcheck` package itself (see plan.md §1a on why those two are separate).
This is plan.md §8's "Download HardTests; select 100 problems; write V0/V1/V2
verifiers" checklist item.

Needs its own venv: `python -m venv .venv` at the repo root, then
`.venv/Scripts/python -m pip install datasets huggingface_hub`. Not added to
`pyproject.toml` — those are heavy, C1-only dependencies the `envcheck`
package itself has no use for.

## Files

- `data.py` — downloads and locally caches problems from
  `sigcp/hardtests_problems` (HuggingFace) as JSONL under `c1/data/` (gitignored
  — it's a cache, not something to commit).
- `codeforces.py` — the Codeforces-only pilot pool: joins HardTests problems
  to `deepmind/code_contests` by URL for real V1 material, plus
  `find_validated_python3_solution` (gold-sanity-style: don't trust a
  solution's language label or its first match, check it actually passes).
- `verifiers.py` — `make_v0_grader` / `make_v1_grader` (shared execution via
  `make_grader_from_tests`). See the module docstring for the sandboxing
  caveat before pointing this at anything you don't trust.

## Status

Pilot scope: Codeforces problems only (confirmed with the user - see
`docs/LEARNING_LOG.md`'s "Resolved V1" entry for why other platforms don't
have a real V1 distinct from V0).

**The 150-problem pilot pool is built and cached**
(`data/validated_codeforces_pool.jsonl`, gitignored): every entry has a
HardTests row (V0 material), a matched `code_contests` row (V1 material),
and a `validated_solution` confirmed to score 1.0 on both V0 and V1 -
plan.md §8's "select 100 problems; write V0/V1 verifiers" checklist item,
done for real. Build it (or rebuild after a code change) with
`c1.codeforces.build_validated_pool(target_count=150)` - takes ~13 minutes,
mostly subprocess spawns for grading.

Not yet done: V2 (`sigcp/hardtests_tests` - schema is known, `HackGen`
confirmed real, no row decoded yet) and V3 (needs C2's certified-adversary
work, plan.md §3 - not started).
