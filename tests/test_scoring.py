import pytest

from envcheck.core.types import Evidence, ProbeResult, Verdict
from envcheck.scoring import score_environment, score_task


def _result(task_id: str, probe: str, verdict: Verdict, *, passed: bool = True) -> ProbeResult:
    return ProbeResult(
        task_id=task_id,
        probe=probe,
        verdict=verdict,
        evidence=[Evidence(probe=probe, task_id=task_id, passed=passed, detail="x")],
    )


def test_score_task_worst_wins():
    results = [
        _result("t1", "gold_sanity", Verdict.KEEP),
        _result("t1", "hackability", Verdict.FIX, passed=False),
    ]

    task_score = score_task(results)

    assert task_score.verdict == Verdict.FIX


def test_score_task_drop_beats_fix_and_keep():
    results = [
        _result("t1", "gold_sanity", Verdict.DROP, passed=False),
        _result("t1", "hackability", Verdict.KEEP),
    ]

    assert score_task(results).verdict == Verdict.DROP


def test_score_task_all_keep_stays_keep():
    results = [
        _result("t1", "gold_sanity", Verdict.KEEP),
        _result("t1", "hackability", Verdict.KEEP),
    ]

    assert score_task(results).verdict == Verdict.KEEP


def test_score_task_rejects_empty_input():
    with pytest.raises(ValueError):
        score_task([])


def test_score_task_rejects_mismatched_task_ids():
    results = [
        _result("t1", "gold_sanity", Verdict.KEEP),
        _result("t2", "hackability", Verdict.KEEP),
    ]
    with pytest.raises(ValueError):
        score_task(results)


def test_score_environment_axes_and_trust_score():
    # t1: both probes clean. t2: gold_sanity drops it, hackability never ran
    # (a broken gate means there's no point attacking it). t3: hackability
    # flags a partial hack, gold_sanity is clean.
    t1 = score_task(
        [
            _result("t1", "gold_sanity", Verdict.KEEP),
            _result("t1", "hackability", Verdict.KEEP),
        ]
    )
    t2 = score_task([_result("t2", "gold_sanity", Verdict.DROP, passed=False)])
    t3 = score_task(
        [
            _result("t3", "gold_sanity", Verdict.KEEP),
            _result("t3", "hackability", Verdict.FIX, passed=False),
        ]
    )

    env_score = score_environment([t1, t2, t3])

    gold_axis = env_score.axes["gold_sanity"]
    assert gold_axis.tasks_run == 3
    assert gold_axis.tasks_flagged == 1  # only t2's gold_sanity verdict was non-KEEP
    assert gold_axis.flagged_rate == pytest.approx(1 / 3)

    hack_axis = env_score.axes["hackability"]
    assert hack_axis.tasks_run == 2  # only t1 and t3 had a hackability probe result
    assert hack_axis.tasks_flagged == 1
    assert hack_axis.finding_rate == pytest.approx(1 / 2)

    # trust_score: KEEP=1.0, DROP=0.0, FIX=0.5 -> (1.0 + 0.0 + 0.5) / 3
    assert env_score.trust_score == pytest.approx(0.5)

    counts = env_score.verdict_counts()
    assert counts[Verdict.KEEP] == 1
    assert counts[Verdict.FIX] == 1
    assert counts[Verdict.DROP] == 1


def test_score_environment_rejects_empty_input():
    with pytest.raises(ValueError):
        score_environment([])
