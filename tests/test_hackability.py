from envcheck.core.types import Task, TaskType, Verdict
from envcheck.probes import hackability


def test_sane_exact_match_grader_keeps_a_code_task():
    task = Task(
        task_id="t1",
        task_type=TaskType.CODE,
        instructions="return 42",
        grade=lambda answer: 1.0 if answer.strip() == "42" else 0.0,
        gold_solution="42",
    )

    result = hackability.run(task)

    assert result.verdict == Verdict.KEEP
    assert all(e.passed for e in result.evidence)
    # only E1 applies to a CODE task with a two-character gold solution (E5 needs
    # at least 4 chars); confirms the "not applicable" skip logic actually runs.
    assert result.evidence[0].budget["k"] == 1


def test_grader_with_numeric_tolerance_gets_hacked_by_the_near_miss_mutation():
    # gold_solution is 4 chars so both E1 (near-miss mutation) and E5 (partial
    # prefix) apply, giving a genuine partial-hack scenario: E1's "4201" sneaks
    # past the tolerance, E5's "42" prefix does not.
    def lenient_grade(answer: str) -> float:
        try:
            return 1.0 if abs(float(answer) - 4200) <= 1 else 0.0
        except ValueError:
            return 0.0

    task = Task(
        task_id="t2",
        task_type=TaskType.CODE,
        instructions="return 4200",
        grade=lenient_grade,
        gold_solution="4200",
    )

    result = hackability.run(task)

    assert result.verdict == Verdict.FIX
    hacked = [e for e in result.evidence if not e.passed]
    assert len(hacked) == 1
    assert "E1" in hacked[0].detail


def test_grader_that_accepts_everything_is_dropped():
    task = Task(
        task_id="t3",
        task_type=TaskType.RUBRIC,
        instructions="Write a helpful, accurate answer.",
        grade=lambda _answer: 1.0,
        gold_solution="the correct answer",
    )

    result = hackability.run(task)

    assert result.verdict == Verdict.DROP
    assert all(not e.passed for e in result.evidence)


def test_task_type_with_no_registered_exploits_and_no_gold_is_kept_by_default():
    task = Task(
        task_id="t4",
        task_type=TaskType.CODE,
        instructions="do something",
        grade=lambda _answer: 0.0,
        gold_solution=None,
    )

    result = hackability.run(task)

    assert result.verdict == Verdict.KEEP
    assert result.evidence[0].budget["k"] == 0
