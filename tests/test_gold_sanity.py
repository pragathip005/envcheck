from envcheck.core.types import Task, TaskType, Verdict
from envcheck.probes import gold_sanity


def test_sane_grader_keeps_task():
    task = Task(
        task_id="t1",
        task_type=TaskType.CODE,
        instructions="return 42",
        grade=lambda answer: 1.0 if answer.strip() == "42" else 0.0,
        gold_solution="42",
    )

    result = gold_sanity.run(task)

    assert result.verdict == Verdict.KEEP
    assert all(e.passed for e in result.evidence)


def test_lenient_grader_that_accepts_a_null_answer_is_dropped():
    task = Task(
        task_id="t2",
        task_type=TaskType.CODE,
        instructions="return 42",
        grade=lambda _answer: 1.0,  # always passes, regardless of input
        gold_solution="42",
    )

    result = gold_sanity.run(task)

    assert result.verdict == Verdict.DROP
    assert not result.evidence[1].passed  # the null-answer check is the one that fails


def test_broken_grader_that_rejects_the_gold_solution_is_dropped():
    task = Task(
        task_id="t3",
        task_type=TaskType.CODE,
        instructions="return 42",
        grade=lambda _answer: 0.0,  # never passes, even the gold solution
        gold_solution="42",
    )

    result = gold_sanity.run(task)

    assert result.verdict == Verdict.DROP
    assert not result.evidence[0].passed  # the gold-solution check is the one that fails


def test_missing_gold_solution_is_flagged_for_fix():
    task = Task(
        task_id="t4",
        task_type=TaskType.CODE,
        instructions="return 42",
        grade=lambda _answer: 0.0,
        gold_solution=None,
    )

    result = gold_sanity.run(task)

    assert result.verdict == Verdict.FIX
