from __future__ import annotations

from dataclasses import dataclass

from envcheck.core.types import ProbeResult, Verdict

_SEVERITY = {Verdict.KEEP: 0, Verdict.FIX: 1, Verdict.DROP: 2}
_TRUST_WEIGHT = {Verdict.KEEP: 1.0, Verdict.FIX: 0.5, Verdict.DROP: 0.0}


@dataclass(frozen=True)
class TaskScore:
    task_id: str
    verdict: Verdict
    probe_results: list[ProbeResult]


def score_task(probe_results: list[ProbeResult]) -> TaskScore:
    """Combine every probe's local verdict for one task into a single verdict.

    Worst-wins: any DROP drops the task, otherwise any FIX downgrades it,
    otherwise KEEP. This is the only place allowed to make that judgment call -
    probes only ever report their own local opinion plus evidence; combining
    opinions across probes is scoring's job alone (see the architecture's
    design rules in plan.md §3).
    """
    if not probe_results:
        raise ValueError("score_task requires at least one ProbeResult")
    task_ids = {result.task_id for result in probe_results}
    if len(task_ids) != 1:
        raise ValueError(f"all ProbeResults must be for the same task, got {sorted(task_ids)}")

    worst = max((result.verdict for result in probe_results), key=lambda v: _SEVERITY[v])
    return TaskScore(task_id=probe_results[0].task_id, verdict=worst, probe_results=list(probe_results))


@dataclass(frozen=True)
class ProbeAxis:
    """One leaderboard column: how a single probe behaved across every task it ran on."""

    probe: str
    tasks_run: int
    tasks_flagged: int
    checks: int
    findings: int

    @property
    def flagged_rate(self) -> float:
        return self.tasks_flagged / self.tasks_run if self.tasks_run else 0.0

    @property
    def finding_rate(self) -> float:
        return self.findings / self.checks if self.checks else 0.0


@dataclass(frozen=True)
class EnvironmentScore:
    """An environment's audit result.

    `axes` (per-probe rates) is the primary artifact per the architecture's
    design rules; `trust_score` is a rough, explicitly secondary summary
    (KEEP=1.0, FIX=0.5, DROP=0.0, averaged across tasks) and should never be
    reported alone - see plan.md §3 on why collapsing every axis into one
    scalar invites the same Goodharting this tool exists to catch.
    """

    task_scores: list[TaskScore]
    axes: dict[str, ProbeAxis]
    trust_score: float

    def verdict_counts(self) -> dict[Verdict, int]:
        counts = {verdict: 0 for verdict in Verdict}
        for task_score in self.task_scores:
            counts[task_score.verdict] += 1
        return counts


def score_environment(task_scores: list[TaskScore]) -> EnvironmentScore:
    if not task_scores:
        raise ValueError("score_environment requires at least one TaskScore")

    per_probe: dict[str, list[ProbeResult]] = {}
    for task_score in task_scores:
        for probe_result in task_score.probe_results:
            per_probe.setdefault(probe_result.probe, []).append(probe_result)

    axes: dict[str, ProbeAxis] = {
        probe_name: ProbeAxis(
            probe=probe_name,
            tasks_run=len(results),
            tasks_flagged=sum(1 for r in results if r.verdict is not Verdict.KEEP),
            checks=sum(len(r.evidence) for r in results),
            findings=sum(1 for r in results for e in r.evidence if not e.passed),
        )
        for probe_name, results in per_probe.items()
    }

    trust_score = sum(_TRUST_WEIGHT[ts.verdict] for ts in task_scores) / len(task_scores)

    return EnvironmentScore(task_scores=list(task_scores), axes=axes, trust_score=trust_score)
