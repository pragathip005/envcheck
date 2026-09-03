# Labelling pilot — how to actually do it

The protocol (what question you're answering, the decision rule) is in
`docs/labelling_protocol.md`. Read that first. This file is just the
mechanics.

## What's here

- `batch.json` — 20 real items to label: 16 from `envcheck`'s exploit pack
  (deterministic, genuinely-wrong-by-construction mutations of a real gold
  solution) and 4 real solver attempts (Groq, asked to actually solve the
  problem — these may or may not be correct, that's the point). Each item
  is `{item_id, instructions, candidate}` - deliberately no source field,
  so labelling stays blind per the protocol.
- `answer_key.json` — where each item actually came from. **Don't open this
  until after both of you have finished labelling** - it exists for
  scoring afterwards, not for you to check yourself against while working.
- `labels_blitz.json`, `labels_pragathi.json` — one each, every item mapped
  to `null` right now. Fill in your own file only.

## Doing the labelling

1. Open `batch.json` and your own `labels_<you>.json` side by side.
2. For each item in the batch, read `instructions` and `candidate`, decide
   CORRECT / WRONG / UNSURE per `docs/labelling_protocol.md`, and replace
   that item's `null` in your labels file with the string.
3. Don't discuss items with each other until you've both finished a
   complete pass.
4. Save.

## Checking agreement

Once both files are fully filled in:

```
python -m c1.labelling.kappa blitz pragathi
```

This prints Cohen's κ and lists every item you disagreed on. See
`docs/labelling_protocol.md` for what to do with the result either way.

## Regenerating or scaling up the batch

```python
from c1.codeforces import build_validated_pool
from c1.labelling.generate import build_labelling_batch

pool = build_validated_pool(target_count=20)  # or however many
build_labelling_batch(pool)
```

Note: `run_solver_ensemble` calls are paced 3s apart to avoid the free-tier
rate-limit flakiness hit while building this (4-5 out of 8 calls failed
without pacing; retrying the identical call in isolation right after always
succeeded, confirming it wasn't a real request problem, just burst load
against a free tier). Even with pacing, expect the occasional dropped
solver item at this batch size - a failed call is skipped, not faked, so
you may get slightly fewer solver-sourced items than pool problems. Not
worth chasing further at this scale; consider more pacing or a paid tier
if it matters more at full scale.
