from envcheck.core.types import Evidence, ProbeResult, Verdict
from envcheck.report import render_text, to_dict
from envcheck.scoring import score_environment, score_task


def _result(task_id: str, probe: str, verdict: Verdict, *, passed: bool = True) -> ProbeResult:
    return ProbeResult(
        task_id=task_id,
        probe=probe,
        verdict=verdict,
        evidence=[Evidence(probe=probe, task_id=task_id, passed=passed, detail="detail-" + probe)],
    )


def _env_score():
    t1 = score_task([_result("t1", "gold_sanity", Verdict.KEEP)])
    t2 = score_task([_result("t2", "gold_sanity", Verdict.DROP, passed=False)])
    return score_environment([t1, t2])


def test_to_dict_structure():
    data = to_dict(_env_score())

    assert data["trust_score"] == 0.5
    assert data["verdict_counts"] == {"keep": 1, "fix": 0, "drop": 1}
    assert data["axes"]["gold_sanity"]["tasks_run"] == 2
    assert data["axes"]["gold_sanity"]["tasks_flagged"] == 1
    assert data["tasks"][0]["task_id"] == "t1"
    assert data["tasks"][1]["probes"][0]["evidence"][0]["detail"] == "detail-gold_sanity"


def test_render_text_leads_with_axes_and_ends_with_trust_score():
    text = render_text(_env_score())

    assert "envcheck report" in text
    assert "per-probe axes:" in text
    assert "gold_sanity" in text
    lines = text.splitlines()
    trust_line_index = next(i for i, line in enumerate(lines) if "trust_score" in line)
    axes_line_index = next(i for i, line in enumerate(lines) if "gold_sanity" in line)
    assert axes_line_index < trust_line_index
    assert "0.500" in text
