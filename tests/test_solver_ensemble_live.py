"""Live integration test - real API calls to both configured providers, and
a realistic demonstration of the whole mechanism: run an ensemble against a
lenient "before" grader and a strict "after" grader (simulating a verifier
patch), and check whether the validity constraint would accept that patch.
"""

import os

import pytest

from envcheck.probes.solver_ensemble import (
    Solver,
    check_validity_constraint,
    ensemble_pass_rate,
    run_solver_ensemble,
)

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GROQ_API_KEY") and os.environ.get("GEMINI_API_KEY")),
    reason="requires real GROQ_API_KEY and GEMINI_API_KEY in .env - this test makes live API calls",
)

_SOLVERS = [
    Solver(model="groq/openai/gpt-oss-120b", style="Answer directly and concisely."),
    Solver(model="gemini/gemini-3.6-flash", style="Think step by step, then give the final answer."),
]


def test_real_ensemble_spans_two_distinct_model_families():
    candidates = run_solver_ensemble("Compute 17 * 23 and reply with just the number.", _SOLVERS)

    assert set(candidates) == {
        "groq/openai/gpt-oss-120b (Answer directly and concisely.)",
        "gemini/gemini-3.6-flash (Think step by step, then give the final answer.)",
    }
    assert all(candidates.values())  # both members actually returned something


def test_real_validity_constraint_catches_an_overly_strict_patch():
    candidates = run_solver_ensemble("Compute 17 * 23 and reply with just the number.", _SOLVERS)

    lenient_grade = lambda s: 1.0 if "391" in s else 0.0  # noqa: E731 - the "before" verifier
    strict_grade = lambda s: 1.0 if s.strip() == "391" else 0.0  # noqa: E731 - the "after" (patched) verifier

    before_rate = ensemble_pass_rate(candidates, lenient_grade)
    after_rate = ensemble_pass_rate(candidates, strict_grade)

    assert before_rate == 1.0  # both models get trivial arithmetic right

    # The strict grader is a stand-in for an over-tightened patch: real
    # models rarely reply with the bare digits despite being asked to, so
    # this "patch" should show a real drop, and epsilon=0 should catch it.
    check = check_validity_constraint(before_rate, after_rate, epsilon=0.0)
    assert check.drop >= 0
    if after_rate < before_rate:
        assert check.holds is False
