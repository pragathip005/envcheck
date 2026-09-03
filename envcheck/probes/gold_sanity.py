from __future__ import annotations

from envcheck.core.types import Evidence, ProbeResult, Task, Verdict

PROBE_NAME = "gold_sanity"


def run(task: Task, pass_threshold: float = 0.999, null_answer: str = "") -> ProbeResult:
    """The QC gate that runs before anything else: does the known-correct answer
    actually pass this task's grader, and does an empty/garbage answer fail it?

    If either check fails, the grader is broken independent of any adversarial
    effort, so there is no point running the other probes against this task yet.
    """
    evidence: list[Evidence] = []

    if task.gold_solution is None:
        evidence.append(
            Evidence(
                probe=PROBE_NAME,
                task_id=task.task_id,
                passed=False,
                detail="no gold solution provided; cannot run the gold-sanity gate",
            )
        )
        return ProbeResult(task.task_id, PROBE_NAME, Verdict.FIX, evidence)

    gold_score = task.grade(task.gold_solution)
    gold_ok = gold_score >= pass_threshold
    evidence.append(
        Evidence(
            probe=PROBE_NAME,
            task_id=task.task_id,
            passed=gold_ok,
            detail=f"gold solution scored {gold_score:.3f} (need >= {pass_threshold})",
            budget={"pass_threshold": pass_threshold},
        )
    )

    null_score = task.grade(null_answer)
    null_ok = null_score < pass_threshold
    evidence.append(
        Evidence(
            probe=PROBE_NAME,
            task_id=task.task_id,
            passed=null_ok,
            detail=f"null answer scored {null_score:.3f} (must stay below {pass_threshold})",
            budget={"pass_threshold": pass_threshold},
        )
    )

    verdict = Verdict.KEEP if (gold_ok and null_ok) else Verdict.DROP
    return ProbeResult(task.task_id, PROBE_NAME, verdict, evidence)
