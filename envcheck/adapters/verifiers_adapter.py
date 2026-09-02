from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from typing import Any

from verifiers.legacy import Rubric, State

from envcheck.core.types import Task, TaskType


def load_tasks(
    dataset: Iterable[Mapping[str, Any]],
    rubric: Rubric,
    task_type: TaskType = TaskType.CODE,
    id_field: str = "id",
    prompt_field: str = "question",
    answer_field: str = "answer",
    gold_solution_field: str | None = None,
) -> list[Task]:
    """Convert a verifiers-format dataset + Rubric into standard envcheck Tasks.

    `Rubric.score_rollout` is verifiers' real scoring entry point, built around a
    live rollout's State. envcheck never runs a rollout here: it builds the same
    State shape by hand around a *given* candidate completion, so a hand-crafted
    or adversary-generated answer gets scored exactly the way the environment
    would score a model's answer, without sampling a model at all.

    `gold_solution` defaults to the row's answer field, which is only a valid
    submittable completion for environments where the reference answer and the
    expected completion are the same string (exact-match / short-answer style).
    For environments where `answer` is grading metadata rather than a candidate
    completion (e.g. a code task's answer is a test spec, not a patch), pass a
    separate `gold_solution_field` pointing at the actual reference solution.
    """
    tasks: list[Task] = []
    for index, row in enumerate(dataset):
        task_id = str(row.get(id_field, index))
        prompt = row.get(prompt_field, "")
        answer = row.get(answer_field)
        gold = row.get(gold_solution_field) if gold_solution_field else answer

        def grade(candidate: str, *, _row=row, _prompt=prompt, _answer=answer) -> float:
            state = State.for_task(_row)
            state["prompt"] = _prompt
            state["answer"] = _answer
            state["completion"] = candidate
            asyncio.run(rubric.score_rollout(state))
            return float(state["reward"])

        tasks.append(
            Task(
                task_id=task_id,
                task_type=task_type,
                instructions=str(prompt),
                grade=grade,
                gold_solution=str(gold) if gold is not None else None,
            )
        )
    return tasks
