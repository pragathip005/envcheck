from __future__ import annotations

from dataclasses import dataclass

from envcheck.core.types import Evidence, Grader

PROBE_NAME = "certify"


@dataclass(frozen=True)
class CertificationResult:
    """Answers a different question than ProbeResult: not "is this task's
    grader trustworthy" (KEEP/FIX/DROP), but "is this specific candidate a
    genuine exploit, or a false alarm" - so it gets its own small result type
    instead of forcing that verdict shape onto a question it wasn't built for.
    """

    task_id: str
    is_genuine_exploit: bool
    evidence: Evidence


def certify_gold_diff(
    task_id: str,
    candidate: str,
    narrow_grade: Grader,
    broad_grade: Grader,
    pass_threshold: float = 0.999,
) -> CertificationResult:
    """C2's gold-diff certification path (plan.md §3): the LLM-free half of
    "every hack passed to the fixer must fail a gold-diff or cross-family
    judge check" - decide whether a hacker-reported "hack" is a genuine
    exploit before it's trusted enough to forward to a fixer.

    `narrow_grade` is the check the hack allegedly gamed (e.g. V0, public
    tests only); `broad_grade` is an independent, harder-to-satisfy check on
    the same candidate (e.g. V1, public+private tests). A candidate that
    passes the narrow grader but fails the broad one has overfit to the
    narrow check - a genuine exploit. One that passes both isn't a hack at
    all: it may be a real, if unexpected, correct solution, or the "hack"
    claim itself was wrong either way, certifying it as an exploit would be
    a false positive that risks the fixer over-tightening the verifier
    against something that was never actually broken.

    The other half (a cross-family LLM judge check) needs an API key and
    lives separately - see envcheck/probes/certify.py's future companion,
    not yet built.
    """
    narrow_score = narrow_grade(candidate)
    broad_score = broad_grade(candidate)
    narrow_pass = narrow_score >= pass_threshold
    broad_pass = broad_score >= pass_threshold

    is_genuine_exploit = narrow_pass and not broad_pass

    if is_genuine_exploit:
        detail = f"narrow={narrow_score:.3f} broad={broad_score:.3f}: certified as a genuine exploit"
    elif broad_pass:
        detail = (
            f"narrow={narrow_score:.3f} broad={broad_score:.3f}: NOT certified - "
            "passes both checks, likely a real solution rather than a hack"
        )
    else:
        detail = (
            f"narrow={narrow_score:.3f} broad={broad_score:.3f}: NOT certified - "
            "fails the narrow check too, so it isn't actually a hack of it"
        )

    evidence = Evidence(
        probe=PROBE_NAME,
        task_id=task_id,
        passed=not is_genuine_exploit,
        detail=detail,
        budget={"pass_threshold": pass_threshold, "method": "gold_diff"},
    )
    return CertificationResult(task_id, is_genuine_exploit, evidence)
