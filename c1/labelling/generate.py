"""Builds the labelling pilot batch: a mix of real solver attempts and
deterministic exploit-pack "genuinely wrong" candidates, for two people to
independently label CORRECT/WRONG/UNSURE before any automated judge is
trusted (docs/labelling_protocol.md has the actual protocol).

Candidates are never executed here. c1/verifiers.py's graders run
candidate code as a bare, unsandboxed subprocess - explicitly documented
there as unsafe for untrusted (model-generated) code on this machine.
Human labelling reads code, it doesn't need to run it, so this sidesteps
that constraint entirely instead of working around it.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

from envcheck.core.types import Task, TaskType
from envcheck.exploits.pack_v0 import e1_near_miss_mutation, e5_partial_prefix
from envcheck.probes.solver_ensemble import Solver, run_solver_ensemble

BATCH_DIR = Path(__file__).parent
BATCH_FILE = BATCH_DIR / "batch.json"
ANSWER_KEY_FILE = BATCH_DIR / "answer_key.json"

_EXPLOITS = [("E1", e1_near_miss_mutation), ("E5", e5_partial_prefix)]


def _never_called(_candidate: str) -> float:
    # Task.grade is a required field, but neither e1 nor e5 (both mutate/
    # truncate task.gold_solution directly) ever calls it - a real
    # placeholder would risk implying candidates get graded here, which
    # they deliberately don't.
    raise AssertionError("grade() should never be called during batch generation")


def build_labelling_batch(
    pool: list[dict],
    solver_model: str = "groq/openai/gpt-oss-120b",
    seed: int = 42,
) -> None:
    """Writes BATCH_FILE (labeller-facing: item_id, instructions, candidate -
    no source information) and ANSWER_KEY_FILE (item_id -> where it came
    from, kept separate so labelling stays blind to source per the protocol).
    """
    items: list[dict] = []
    answer_key: dict[str, dict] = {}

    for i, entry in enumerate(pool):
        if i > 0:
            # Firing solver calls back-to-back with no pacing hit real,
            # transient provider throttling in practice: 5/8 calls failed
            # even with run_solver_ensemble's own num_retries+timeout, and
            # the identical call succeeded when reproduced in isolation
            # right after. This isn't about num_retries (that handles one
            # call's own transient errors) - it's sustained load across many
            # calls in a tight loop, which needs pacing between them instead.
            time.sleep(3.0)
        pid = entry["hardtests"]["pid"]
        instructions = entry["hardtests"]["question_content"]
        gold = entry["validated_solution"]
        task = Task(
            task_id=pid,
            task_type=TaskType.CODE,
            instructions=instructions,
            grade=_never_called,
            gold_solution=gold,
        )

        for exploit_id, generate in _EXPLOITS:
            candidate = generate(task)
            if candidate is None:
                continue  # exploit declined (e.g. gold too short for E5)
            item_id = f"{pid}-{exploit_id}"
            items.append({"item_id": item_id, "instructions": instructions, "candidate": candidate})
            answer_key[item_id] = {"source": exploit_id, "problem_id": pid}

        ensemble = run_solver_ensemble(instructions, [Solver(model=solver_model)])
        for solver_label, candidate in ensemble.items():
            if not candidate:
                continue  # solver call failed even after retries - skip, don't fabricate an item
            item_id = f"{pid}-solver"
            items.append({"item_id": item_id, "instructions": instructions, "candidate": candidate})
            answer_key[item_id] = {"source": "solver_ensemble", "problem_id": pid, "model": solver_label}

    random.Random(seed).shuffle(items)  # break per-problem grouping so order doesn't leak the source

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    BATCH_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")
    ANSWER_KEY_FILE.write_text(json.dumps(answer_key, indent=2), encoding="utf-8")
    print(f"wrote {len(items)} items to {BATCH_FILE}")


def make_labels_template(labeler_name: str) -> Path:
    """Creates c1/labelling/labels_<labeler_name>.json - every item_id from
    the batch mapped to null, ready for that person to fill in independently.
    Refuses to overwrite an existing (possibly already-in-progress) file.
    """
    items = json.loads(BATCH_FILE.read_text(encoding="utf-8"))
    path = BATCH_DIR / f"labels_{labeler_name}.json"
    if path.exists():
        raise FileExistsError(f"{path} already exists - not overwriting in-progress labels")
    labels = {item["item_id"]: None for item in items}
    path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
    return path
