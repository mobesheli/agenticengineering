"""Parallel trial execution with one isolated environment per attempt."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Protocol

from .environment import EvalEnvironment, provision, teardown
from .models import EvalTask, Transcript, Trial
from .reviewer import ComplianceReviewer


class Reviewer(Protocol):
    async def run(self, task: EvalTask) -> Transcript: ...


ReviewerFactory = Callable[[EvalEnvironment], Reviewer]


async def run_trial(
    reviewer_factory: ReviewerFactory, task: EvalTask, index: int
) -> Trial:
    environment = await provision(task)
    try:
        reviewer = reviewer_factory(environment)
        transcript = await reviewer.run(task)
        return Trial(
            task_id=task.task_id,
            task_kind=task.kind,
            index=index,
            transcript=transcript,
            final_state=await environment.snapshot(),
        )
    finally:
        await teardown(environment)


async def run_suite(
    tasks: Sequence[EvalTask],
    k: int,
    reviewer_factory: ReviewerFactory = ComplianceReviewer,
    *,
    max_concurrency: int = 20,
) -> list[Trial]:
    if k < 1:
        raise ValueError("k must be at least one")
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least one")
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded(task: EvalTask, index: int) -> Trial:
        async with semaphore:
            return await run_trial(reviewer_factory, task, index)

    jobs = [bounded(task, index) for task in tasks for index in range(k)]
    return list(await asyncio.gather(*jobs))
