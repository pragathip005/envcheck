# envcheck

An independent QC gate for RL training environments.

Environment supply for RL-trained LLMs is moving from hundreds of hand-built
tasks to millions of synthesized ones, and published audits show a large
fraction of tasks in well-known environments accept wrong solutions. Vendors
grade themselves; labs audit internally and don't share results. envcheck is
the independent, automated measurement layer: run it before training, get a
per-task verdict (KEEP / FIX / DROP) and an environment-level Trust Score, and
stop paying training compute to learn the wrong thing.

Status: early scaffolding (Phase 0). Not yet usable against real environments.

## Architecture

```
envcheck/
  core/       # shared Task / Evidence / Verdict data model
  adapters/   # translates each environment format into the standard Task shape
  probes/     # independent inspectors: gold_sanity, hackability, judge_bias, difficulty, diversity
  exploits/   # versioned attack library (E1-E14)
  scoring/    # combines probe verdicts into a per-task verdict + Trust Score
  report/     # JSON + HTML report, CI exit codes
  repair/     # (v1.0) propose and re-verify fixes for FIX-verdict tasks
  cli.py
bench/        # EnvTrust-Bench: environment manifests, ground-truth labels, leaderboard
paper/
```

Every probe is independent and returns `(task_id, verdict, evidence)`; score
aggregation is a separate, later step. Every claim carries the attack budget
used (K candidates, model, temperature) - scores are probabilistic, never a
proof that a task is unhackable.

## Development

```
pip install -e ".[dev]"
pytest
envcheck version
```
