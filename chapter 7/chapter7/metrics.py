"""From graded trials to suite scores, with the uncertainty that belongs to them."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, stdev

from pydantic import BaseModel

from chapter7.graders import TrialGrade
from chapter7.runner import Trial
from chapter7.tasks import EvalTask, TaskKind


def pass_to_k(grades: list[TrialGrade]) -> dict[str, bool]:
    by_task: dict[str, list[bool]] = defaultdict(list)
    for grade in grades:
        by_task[grade.task_id].append(grade.passed)
    return {task_id: all(results) for task_id, results in by_task.items()}


def suite_score(per_task: dict[str, bool]) -> tuple[float, float]:
    n = len(per_task)
    share = sum(per_task.values()) / n
    return share, math.sqrt(share * (1 - share) / n)


def paired_drop(
    baseline: dict[str, bool], candidate: dict[str, bool]
) -> tuple[float, float]:
    drops = [baseline[task_id] - candidate[task_id] for task_id in baseline]
    return mean(drops), stdev(drops) / math.sqrt(len(drops))


def pass_at_k(grades: list[TrialGrade]) -> dict[str, bool]:
    by_task: dict[str, list[bool]] = defaultdict(list)
    for grade in grades:
        by_task[grade.task_id].append(grade.passed)
    return {task_id: any(results) for task_id, results in by_task.items()}


class SuiteResult(BaseModel):
    """What one full run of both suites established."""

    run_id: str
    k: int
    golden: dict[str, bool]
    abuse_failures: set[str]
    single_trial_rate: float
    cost_per_task: float
    seconds_p50: float
    seconds_p95: float
    failures: dict[str, list[str]]

    @property
    def golden_score(self) -> tuple[float, float]:
        return suite_score(self.golden)


def summarize(
    run_id: str,
    tasks: list[EvalTask],
    trials: list[Trial],
    grades: list[TrialGrade],
    k: int,
) -> SuiteResult:
    kinds = {task.task_id: task.kind for task in tasks}
    per_task = pass_to_k(grades)
    golden_grades = [g for g in grades if kinds[g.task_id] == TaskKind.GOLDEN]
    seconds = sorted(trial.seconds for trial in trials)
    failures: dict[str, list[str]] = defaultdict(list)
    for grade in grades:
        for failure in grade.failures:
            if failure not in failures[grade.task_id]:
                failures[grade.task_id].append(failure)
    return SuiteResult(
        run_id=run_id,
        k=k,
        golden={t: ok for t, ok in per_task.items() if kinds[t] == TaskKind.GOLDEN},
        abuse_failures={
            t for t, ok in per_task.items() if kinds[t] == TaskKind.ABUSE and not ok
        },
        single_trial_rate=sum(g.passed for g in golden_grades) / len(golden_grades),
        cost_per_task=sum(trial.cost for trial in trials) / len(trials),
        seconds_p50=seconds[len(seconds) // 2],
        seconds_p95=seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))],
        failures=dict(failures),
    )
