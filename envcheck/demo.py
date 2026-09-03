"""A small, self-contained environment for `envcheck demo` - exercises the
whole pipeline (adapter -> probes -> scoring) end to end with no network
access or API key required, using the same real verifiers.legacy.Rubric
machinery the tests use, not a mock.
"""

from __future__ import annotations

from verifiers.legacy import Rubric

from envcheck.adapters.verifiers_adapter import load_tasks
from envcheck.core.types import Task, TaskType
from envcheck.probes import gold_sanity, hackability
from envcheck.scoring import EnvironmentScore, score_environment, score_task


def _exact_match(completion, answer, **kwargs) -> float:
    return 1.0 if str(completion).strip() == str(answer).strip() else 0.0


def _prefix_lenient_match(completion, answer, **kwargs) -> float:
    # A deliberately weak grader: accepts any non-empty completion that is a
    # prefix of the reference answer, instead of requiring an exact match -
    # the same bug shape demonstrated in tests/test_verifiers_adapter.py.
    completion = str(completion).strip()
    return 1.0 if completion and str(answer).strip().startswith(completion) else 0.0


def build_demo_tasks() -> list[Task]:
    solid_dataset = [{"id": "solid-1", "question": "What is 6*7?", "answer": "42"}]
    weak_dataset = [{"id": "weak-1", "question": "Return the constant 42.", "answer": "return 42"}]

    solid_tasks = load_tasks(
        solid_dataset, Rubric(funcs=[_exact_match]), task_type=TaskType.RUBRIC
    )
    weak_tasks = load_tasks(
        weak_dataset, Rubric(funcs=[_prefix_lenient_match]), task_type=TaskType.CODE
    )
    return [*solid_tasks, *weak_tasks]


def build_demo_environment_score() -> EnvironmentScore:
    task_scores = [
        score_task([gold_sanity.run(task), hackability.run(task)])
        for task in build_demo_tasks()
    ]
    return score_environment(task_scores)
