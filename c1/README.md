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
- `verifiers.py` — `make_v0_grader` / `make_v1_grader` / `make_v2_grader`
  (V0/V1 share execution via `make_grader_from_tests`; V2 additionally runs a
  per-problem `output_judging_function` when one exists, since some problems
  have multiple valid outputs). See the module docstring for the sandboxing
  caveat before pointing this at anything you don't trust.
- `hardtests_tests.py` — decodes real `sigcp/hardtests_tests` rows (V2
  material: `test_cases_kit`, `mapping`, `test_cases`, including the
  adversarial `HackGen` generator) via a local shard download, not streaming
  (streaming this dataset hangs - see `docs/LEARNING_LOG.md`).
- `evilgenie.py` — two of EvilGenie's three hack-rate detectors, ported to
  run without Docker: `classify_test_result` (passed_all /
  passed_visible_only / failed_visible, fed our own V0/holdout grader
  scores) and `judge_solution` (the LLM-judge prompt, routed through
  `litellm` - needs an API key to actually call a model, not yet
  configured). File-modification detection was not ported - it needs a live
  agent editing files in an actual workspace, which doesn't exist yet.

## Status

Pilot scope: Codeforces problems only (confirmed with the user - see
`docs/LEARNING_LOG.md`'s "Resolved V1" entry for why other platforms don't
have a real V1 distinct from V0).

**V0, V1, and V2 are all built and independently verified** against live
data - 15/15 pool problems clean across all three simultaneously, including
3 with a real custom `output_judging_function` (confirming that path, not
just plain exact-match). **The 150-problem pilot pool is built and cached**
(`data/validated_codeforces_pool.jsonl`, gitignored): every entry has a
HardTests row (V0 material), a matched `code_contests` row (V1 material),
and a `validated_solution` confirmed to score 1.0 on both V0 and V1 -
plan.md §8's "select 100 problems; write V0/V1/V2 verifiers" checklist item,
done for real. Build it (or rebuild after a code change) with
`c1.codeforces.build_validated_pool(target_count=150)` - takes ~13 minutes,
mostly subprocess spawns for grading.

**`data/`, and any venv you install `datasets`/`huggingface_hub` into, are
both gitignored and machine-local** - they don't travel with `git pull`.
Rebuild the pool freshly on any new machine rather than expecting the cache
to already be there.

Not yet done at full scale: V2 data has only been fetched for 17/150 pool
problems (a full-pool fetch was attempted and stopped after ~1hr for time,
not correctness - the 121-shard scan is just slow; resume anytime with
`c1.hardtests_tests.fetch_for_pids`, backgrounded). V3 needs C2's
certified-adversary work (plan.md §3) - not started, and doesn't need
Docker/harden-v0 access to prototype the certification *logic* itself
(e.g. a cross-family "is this candidate genuinely wrong" check) against
these same V0/V1/V2 graders as a stand-in execution substrate.
