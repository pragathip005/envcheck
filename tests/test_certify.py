from envcheck.probes.certify import certify_gold_diff


def test_passes_narrow_fails_broad_is_certified_as_a_genuine_exploit():
    # A candidate hardcoded to the narrow (public) tests: 1.0 on narrow,
    # 0.0 on broad (private) tests it never saw.
    result = certify_gold_diff(
        task_id="t1",
        candidate="hardcoded-answer",
        narrow_grade=lambda _c: 1.0,
        broad_grade=lambda _c: 0.0,
    )

    assert result.is_genuine_exploit is True
    assert result.evidence.passed is False  # "passed" = not a genuine exploit
    assert "certified as a genuine exploit" in result.evidence.detail


def test_passes_both_is_not_certified_a_false_alarm():
    # Passes the narrow check AND the independent broad check - not a hack,
    # just an unexpectedly valid solution.
    result = certify_gold_diff(
        task_id="t2",
        candidate="actually-correct",
        narrow_grade=lambda _c: 1.0,
        broad_grade=lambda _c: 1.0,
    )

    assert result.is_genuine_exploit is False
    assert result.evidence.passed is True
    assert "likely a real solution" in result.evidence.detail


def test_fails_narrow_too_is_not_a_hack_of_it():
    result = certify_gold_diff(
        task_id="t3",
        candidate="just-wrong",
        narrow_grade=lambda _c: 0.0,
        broad_grade=lambda _c: 0.0,
    )

    assert result.is_genuine_exploit is False
    assert "isn't actually a hack of it" in result.evidence.detail


def test_evidence_carries_the_pass_threshold_as_budget():
    result = certify_gold_diff(
        task_id="t4",
        candidate="x",
        narrow_grade=lambda _c: 1.0,
        broad_grade=lambda _c: 0.0,
        pass_threshold=0.9,
    )

    assert result.evidence.budget == {"pass_threshold": 0.9, "method": "gold_diff"}
