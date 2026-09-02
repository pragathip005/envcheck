from __future__ import annotations

from envcheck.core.types import Evidence, ProbeResult, Task, Verdict
from envcheck.exploits import EXPLOITS, PACK_VERSION
from envcheck.exploits.base import Exploit

PROBE_NAME = "hackability"


def run(
    task: Task,
    exploits: list[Exploit] | None = None,
    pass_threshold: float = 0.999,
) -> ProbeResult:
    """Try every applicable exploit against a task and see how many genuinely-wrong
    candidates still score as a pass.

    This is adversarial, not exhaustive: a KEEP verdict means none of the
    attempted exploits worked, at the stated attack budget - never proof that
    the task is unhackable. The budget (which exploit-pack version, how many
    exploits were actually attempted) travels with every piece of evidence so
    the claim stays checkable later.
    """
    exploits = EXPLOITS if exploits is None else exploits

    attempts: list[tuple[Exploit, str]] = []
    for exploit in exploits:
        if task.task_type not in exploit.applies_to:
            continue
        candidate = exploit.generate(task)
        if candidate is not None:
            attempts.append((exploit, candidate))

    budget = {
        "exploit_pack_version": PACK_VERSION,
        "k": len(attempts),
        "pass_threshold": pass_threshold,
    }

    if not attempts:
        evidence = [
            Evidence(
                probe=PROBE_NAME,
                task_id=task.task_id,
                passed=True,
                detail="no applicable exploits for this task (missing gold_solution, "
                "or no exploit registered for this task type)",
                budget=budget,
            )
        ]
        return ProbeResult(task.task_id, Verdict.KEEP, evidence)

    evidence = []
    hacked_count = 0
    for exploit, candidate in attempts:
        score = task.grade(candidate)
        hacked = score >= pass_threshold
        hacked_count += hacked
        evidence.append(
            Evidence(
                probe=PROBE_NAME,
                task_id=task.task_id,
                passed=not hacked,
                detail=f"{exploit.id} ({exploit.name}) scored {score:.3f} "
                f"({'HACKED' if hacked else 'held'})",
                budget=budget,
            )
        )

    if hacked_count == len(attempts):
        verdict = Verdict.DROP  # every attempted exploit slipped through
    elif hacked_count > 0:
        verdict = Verdict.FIX
    else:
        verdict = Verdict.KEEP

    return ProbeResult(task.task_id, verdict, evidence)
