from __future__ import annotations

from typing import Any

from envcheck.core.types import Verdict
from envcheck.scoring import EnvironmentScore


def to_dict(env_score: EnvironmentScore) -> dict[str, Any]:
    """JSON-serializable view of an EnvironmentScore."""
    return {
        "trust_score": env_score.trust_score,
        "verdict_counts": {
            verdict.value: count for verdict, count in env_score.verdict_counts().items()
        },
        "axes": {
            name: {
                "tasks_run": axis.tasks_run,
                "tasks_flagged": axis.tasks_flagged,
                "flagged_rate": axis.flagged_rate,
                "checks": axis.checks,
                "findings": axis.findings,
                "finding_rate": axis.finding_rate,
            }
            for name, axis in env_score.axes.items()
        },
        "tasks": [
            {
                "task_id": task_score.task_id,
                "verdict": task_score.verdict.value,
                "probes": [
                    {
                        "probe": probe_result.probe,
                        "verdict": probe_result.verdict.value,
                        "evidence": [
                            {"passed": e.passed, "detail": e.detail, "budget": e.budget}
                            for e in probe_result.evidence
                        ],
                    }
                    for probe_result in task_score.probe_results
                ],
            }
            for task_score in env_score.task_scores
        ],
    }


def render_text(env_score: EnvironmentScore) -> str:
    """A short, human-readable summary. Per-axis columns come first, since
    those are the primary artifact (plan.md §3); the trust score is last and
    labeled as a rough summary, never the headline number.
    """
    counts = env_score.verdict_counts()
    lines = [
        "envcheck report",
        "=" * 40,
        f"tasks: {len(env_score.task_scores)}  "
        f"KEEP={counts[Verdict.KEEP]} FIX={counts[Verdict.FIX]} DROP={counts[Verdict.DROP]}",
        "",
        "per-probe axes:",
    ]
    for name, axis in sorted(env_score.axes.items()):
        lines.append(
            f"  {name}: ran={axis.tasks_run} flagged={axis.tasks_flagged} "
            f"(flagged_rate={axis.flagged_rate:.1%}) "
            f"findings={axis.findings}/{axis.checks} (finding_rate={axis.finding_rate:.1%})"
        )
    lines += [
        "",
        "trust_score (rough summary, KEEP=1.0/FIX=0.5/DROP=0.0 average): "
        f"{env_score.trust_score:.3f}",
    ]
    return "\n".join(lines)
