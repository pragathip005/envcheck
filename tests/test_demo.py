import pytest

from envcheck.core.types import Verdict
from envcheck.demo import build_demo_environment_score


def test_demo_environment_score_matches_hand_worked_expectation():
    # solid-1: exact-match grader, both gold_sanity and hackability hold clean -> KEEP.
    # weak-1: prefix-lenient grader, gold_sanity holds but E5's partial-prefix
    # candidate ("retu") is accepted by the buggy grader -> hackability FIX,
    # worst-wins with gold_sanity's KEEP gives FIX for the task overall.
    env_score = build_demo_environment_score()

    verdicts = {ts.task_id: ts.verdict for ts in env_score.task_scores}
    assert verdicts == {"solid-1": Verdict.KEEP, "weak-1": Verdict.FIX}

    assert env_score.trust_score == pytest.approx(0.75)  # (1.0 + 0.5) / 2

    hackability_axis = env_score.axes["hackability"]
    assert hackability_axis.tasks_run == 2
    assert hackability_axis.tasks_flagged == 1
