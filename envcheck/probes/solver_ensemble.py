"""C2's other two hardening-loop safeguards (plan.md §3): a solver ensemble
standing in for harden-v0's single reference solver, and the validity
constraint that uses it - reject a verifier patch if the ensemble's benign
pass rate drops by more than a tolerance epsilon, so hardening never quietly
breaks the task for genuine solvers along the way.
"""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv

from envcheck.core.types import Grader

load_dotenv()  # picks up .env at the repo root if present; safe to call repeatedly

_SOLVER_PROMPT = """Solve the following task and reply with ONLY your solution - no explanation, no markdown fences, just the raw answer.

{instructions}"""


@dataclass(frozen=True)
class Solver:
    """One ensemble member. plan.md §3 requires the ensemble to vary along
    two axes - ">=2 model families, >=2 solution styles" - so a member is a
    model plus an optional style instruction, not just a model; two members
    can share a model with different styles, or share a style across
    different model families.
    """

    model: str
    style: str = ""

    @property
    def label(self) -> str:
        return f"{self.model} ({self.style})" if self.style else self.model


def run_solver_ensemble(instructions: str, solvers: list[Solver]) -> dict[str, str]:
    """Ask each ensemble member to attempt the task independently. Returns
    each member's raw solution attempt keyed by its label.

    Transient provider errors (rate limits, 503s, timeouts) are retried a
    few times via litellm's own num_retries - confirmed against a real
    Gemini 503 "high demand" error hit while building this, which a bare
    call would otherwise have silently recorded as a genuine model failure.
    Conflating "the provider had a hiccup" with "the model got it wrong"
    would bias the validity constraint against a benign patch that happened
    to hit unlucky timing, not against anything the patch actually did.

    Each attempt also carries its own timeout, capping how long one hung
    attempt can delay the retry that's supposed to route around it -
    without this, num_retries alone doesn't bound total latency: a run
    against a genuinely degraded Gemini during development took nearly 25
    minutes for what should have been a handful of calls, because each slow
    attempt was left to hang before the next retry even started.

    A member that still fails after retries (a real, sustained failure, or a
    non-retryable error like a bad model name) is recorded as an empty
    string rather than dropped - a missing ensemble member should count
    against the pass rate like any other failed attempt, not silently
    shrink the ensemble it's measured against.
    """
    import litellm

    candidates: dict[str, str] = {}
    for solver in solvers:
        prompt = _SOLVER_PROMPT.format(instructions=instructions)
        if solver.style:
            prompt = f"{solver.style}\n\n{prompt}"
        try:
            response = litellm.completion(
                model=solver.model,
                messages=[{"role": "user", "content": prompt}],
                num_retries=3,
                timeout=30.0,
            )
            candidates[solver.label] = response.choices[0].message.content or ""
        except Exception:
            candidates[solver.label] = ""
    return candidates


def ensemble_pass_rate(candidates: dict[str, str], grade: Grader, pass_threshold: float = 0.999) -> float:
    """Fraction of the ensemble's candidate solutions that pass `grade`."""
    if not candidates:
        raise ValueError("ensemble_pass_rate requires at least one candidate")
    passing = sum(1 for solution in candidates.values() if grade(solution) >= pass_threshold)
    return passing / len(candidates)


@dataclass(frozen=True)
class ValidityCheck:
    before_rate: float
    after_rate: float
    epsilon: float
    holds: bool

    @property
    def drop(self) -> float:
        return self.before_rate - self.after_rate


def check_validity_constraint(before_rate: float, after_rate: float, epsilon: float) -> ValidityCheck:
    """C2's validity constraint (plan.md §3): a verifier patch is only
    accepted if the ensemble's benign pass rate doesn't drop by more than
    epsilon. Working in terms of rates (not a single pass/fail) is what lets
    this be swept across multiple epsilon values - plan.md §3's "sweep ε" -
    to produce the ASR-vs-validity Pareto frontier C2 targets, rather than
    baking in one fixed tolerance.

    Rates are typically k/n fractions, so `drop` and `epsilon` can differ by
    a float-rounding sliver even when they're meant to be equal (e.g.
    0.9 - 0.85 == 0.05000000000000004 in IEEE floats) - a boundary sweep
    value would otherwise flip `holds` on rounding noise rather than the
    actual comparison. A tiny absolute tolerance absorbs that without
    meaningfully loosening the constraint itself.
    """
    drop = before_rate - after_rate
    holds = drop <= epsilon + 1e-9
    return ValidityCheck(before_rate=before_rate, after_rate=after_rate, epsilon=epsilon, holds=holds)
