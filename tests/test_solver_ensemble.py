from unittest.mock import MagicMock, patch

import pytest

from envcheck.probes.solver_ensemble import (
    Solver,
    check_validity_constraint,
    ensemble_pass_rate,
    run_solver_ensemble,
)


def _fake_completion(content: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def test_solver_label_includes_style_when_present():
    assert Solver(model="groq/x").label == "groq/x"
    assert Solver(model="groq/x", style="be terse").label == "groq/x (be terse)"


def test_run_solver_ensemble_collects_one_candidate_per_solver():
    solvers = [Solver(model="groq/a"), Solver(model="gemini/b")]
    with patch("litellm.completion", side_effect=[_fake_completion("answer-a"), _fake_completion("answer-b")]):
        candidates = run_solver_ensemble("do the task", solvers)

    assert candidates == {"groq/a": "answer-a", "gemini/b": "answer-b"}


def test_run_solver_ensemble_retries_transient_provider_errors():
    # A real Gemini 503 "high demand" error was hit live while building this;
    # a bare call would have recorded it as a genuine model failure instead
    # of retrying, biasing the validity constraint against a benign patch.
    solvers = [Solver(model="groq/a")]
    with patch("litellm.completion", return_value=_fake_completion("answer-a")) as mock_completion:
        run_solver_ensemble("do the task", solvers)

    assert mock_completion.call_args.kwargs["num_retries"] == 3
    assert mock_completion.call_args.kwargs["timeout"] == 30.0


def test_run_solver_ensemble_keys_by_label_so_same_model_different_styles_dont_collide():
    solvers = [Solver(model="groq/a", style="terse"), Solver(model="groq/a", style="verbose")]
    with patch("litellm.completion", side_effect=[_fake_completion("short"), _fake_completion("long")]):
        candidates = run_solver_ensemble("do the task", solvers)

    assert candidates == {"groq/a (terse)": "short", "groq/a (verbose)": "long"}


def test_run_solver_ensemble_records_a_failed_member_as_empty_string_not_a_crash():
    solvers = [Solver(model="groq/a"), Solver(model="groq/broken")]
    with patch("litellm.completion", side_effect=[_fake_completion("ok"), RuntimeError("rate limited")]):
        candidates = run_solver_ensemble("do the task", solvers)

    assert candidates == {"groq/a": "ok", "groq/broken": ""}


def test_ensemble_pass_rate_computes_the_fraction_that_pass():
    candidates = {"a": "42", "b": "wrong", "c": "42", "d": "42"}
    rate = ensemble_pass_rate(candidates, grade=lambda s: 1.0 if s == "42" else 0.0)
    assert rate == 0.75


def test_ensemble_pass_rate_rejects_an_empty_ensemble():
    with pytest.raises(ValueError):
        ensemble_pass_rate({}, grade=lambda s: 1.0)


def test_validity_constraint_holds_when_drop_is_within_epsilon():
    check = check_validity_constraint(before_rate=0.9, after_rate=0.88, epsilon=0.05)
    assert check.holds is True
    assert check.drop == pytest.approx(0.02)


def test_validity_constraint_holds_at_exactly_epsilon():
    check = check_validity_constraint(before_rate=0.9, after_rate=0.85, epsilon=0.05)
    assert check.holds is True


def test_validity_constraint_fails_when_drop_exceeds_epsilon():
    check = check_validity_constraint(before_rate=0.9, after_rate=0.5, epsilon=0.05)
    assert check.holds is False


def test_validity_constraint_holds_when_pass_rate_improves():
    check = check_validity_constraint(before_rate=0.5, after_rate=0.9, epsilon=0.0)
    assert check.holds is True
    assert check.drop < 0
