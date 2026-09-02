from verifiers.legacy import Rubric

from envcheck.adapters.verifiers_adapter import load_tasks
from envcheck.core.types import TaskType, Verdict
from envcheck.probes import gold_sanity


def exact_match(completion, answer, **kwargs) -> float:
    return 1.0 if str(completion).strip() == str(answer).strip() else 0.0


def test_adapter_wires_a_real_verifiers_rubric_into_gold_sanity():
    dataset = [
        {"id": "q1", "question": "What is 6*7?", "answer": "42"},
        {"id": "q2", "question": "Capital of France?", "answer": "Paris"},
    ]
    rubric = Rubric(funcs=[exact_match])

    tasks = load_tasks(dataset, rubric, task_type=TaskType.RUBRIC)

    assert [t.task_id for t in tasks] == ["q1", "q2"]

    results = [gold_sanity.run(t) for t in tasks]
    assert all(r.verdict == Verdict.KEEP for r in results)


def test_adapter_catches_a_grader_that_accepts_a_null_answer():
    dataset = [{"id": "q1", "question": "What is 6*7?", "answer": "42"}]

    def always_pass(completion, answer, **kwargs) -> float:
        return 1.0

    rubric = Rubric(funcs=[always_pass])
    tasks = load_tasks(dataset, rubric, task_type=TaskType.RUBRIC)

    result = gold_sanity.run(tasks[0])

    assert result.verdict == Verdict.DROP
    assert not result.evidence[1].passed  # the null-answer check is the one that fails
