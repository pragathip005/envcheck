"""Combines every probe's ProbeResult for a task into one KEEP/FIX/DROP verdict,
then rolls all task verdicts up into one environment-level Trust Score. This is
the only module allowed to hold scoring-policy opinions (thresholds, weights).
"""

from envcheck.scoring.types import (
    EnvironmentScore,
    ProbeAxis,
    TaskScore,
    score_environment,
    score_task,
)

__all__ = [
    "EnvironmentScore",
    "ProbeAxis",
    "TaskScore",
    "score_environment",
    "score_task",
]
