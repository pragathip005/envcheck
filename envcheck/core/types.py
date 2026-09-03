from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class TaskType(str, Enum):
    CODE = "code"
    TOOL_USE = "tool_use"
    RUBRIC = "rubric"


class Verdict(str, Enum):
    KEEP = "keep"
    FIX = "fix"
    DROP = "drop"


Grader = Callable[[str], float]
"""Scores a candidate solution/answer against one task, returning a reward in [0, 1].

An adapter is responsible for closing over whatever the real grading mechanism is
(running hidden tests, replaying a tool-use trajectory, calling an LLM judge) and
exposing it through this one flat signature so probes never need to know the
underlying environment format.
"""


@dataclass(frozen=True)
class Task:
    task_id: str
    task_type: TaskType
    instructions: str
    grade: Grader
    gold_solution: str | None = None


@dataclass(frozen=True)
class Evidence:
    probe: str
    task_id: str
    passed: bool
    detail: str
    budget: dict[str, Any] = field(default_factory=dict)
    """Attack budget behind this evidence (e.g. {"k": 8, "model": "...", "temperature": 0.7}).

    A probe's claim is only ever "we tried this much and found/didn't find a problem" -
    never a proof. The budget is what makes that claim checkable and reproducible.
    """


@dataclass(frozen=True)
class ProbeResult:
    task_id: str
    probe: str
    verdict: Verdict
    evidence: list[Evidence]
