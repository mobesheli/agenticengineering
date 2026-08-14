"""Reliability, uncertainty, cost, and latency aggregation."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone

from .models import SuiteResult, TaskKind, Trial, TrialGrade


def theoretical_pass_at_k(probability: float, k: int) -> float:
    _validate_probability(probability, k)
    return 1 - (1 - probability) ** k


def theoretical_pass_to_k(probability: float, k: int) -> float:
    _validate_probability(probability, k)
    return probability**k


def _validate_probability(probability: float, k: int) -> None:
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between zero and one")
    if k < 1:
        raise ValueError("k must be at least one")


def task_reliability(
    grades: Sequence[TrialGrade],
) -> tuple[dict[str, float], dict[str, float]]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for grade in grades:
        grouped[grade.task_id].append(grade.passed)
    pass_at = {task_id: float(any(outcomes)) for task_id, outcomes in grouped.items()}
    pass_to = {task_id: float(all(outcomes)) for task_id, outcomes in grouped.items()}
    return pass_at, pass_to


def suite_score(per_task: dict[str, float]) -> tuple[float, float]:
    if not per_task:
        return 0.0, 0.0
    mean = sum(per_task.values()) / len(per_task)
    standard_error = math.sqrt(mean * (1 - mean) / len(per_task))
    return mean, standard_error


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_suite_result(
    trials: Sequence[Trial],
    grades: Sequence[TrialGrade],
    *,
    judge_cost: float = 0.0,
    human_review_cost: float = 0.0,
    run_id: str | None = None,
) -> SuiteResult:
    if len(trials) != len(grades):
        raise ValueError("every trial must have exactly one grade")
    trial_keys = {(trial.task_id, trial.index) for trial in trials}
    grade_keys = {(grade.task_id, grade.index) for grade in grades}
    if trial_keys != grade_keys:
        raise ValueError("trial and grade identifiers do not align")

    pass_at, pass_to = task_reliability(grades)
    kinds = {trial.task_id: trial.task_kind for trial in trials}
    golden = {task_id: score for task_id, score in pass_to.items() if kinds[task_id] == TaskKind.GOLDEN}
    abuse = {task_id: score for task_id, score in pass_to.items() if kinds[task_id] == TaskKind.ABUSE}
    quality_mean, quality_se = suite_score(golden)
    abuse_mean, _ = suite_score(abuse)
    k = max((sum(trial.task_id == task_id for trial in trials) for task_id in pass_to), default=1)
    base_cost = sum(trial.transcript.model_cost for trial in trials)
    denominator = len(trials) or 1
    failures = [grade.model_dump(mode="json") for grade in grades if not grade.passed]
    return SuiteResult(
        run_id=run_id or datetime.now(timezone.utc).strftime("eval-%Y%m%dT%H%M%SZ"),
        trial_count=len(trials),
        task_count=len(pass_to),
        k=k,
        quality_mean=quality_mean,
        quality_se=quality_se,
        golden_pass_rate=quality_mean,
        abuse_pass_rate=abuse_mean,
        pass_at_k=sum(pass_at.values()) / len(pass_at) if pass_at else 0.0,
        pass_to_k=sum(pass_to.values()) / len(pass_to) if pass_to else 0.0,
        cost_per_task=(base_cost + judge_cost + human_review_cost) / denominator,
        latency_p50=percentile([trial.transcript.latency_seconds for trial in trials], 0.50),
        latency_p95=percentile([trial.transcript.latency_seconds for trial in trials], 0.95),
        artifacts={
            "golden_suite_results": {"per_task": golden, "mean": quality_mean, "standard_error": quality_se},
            "abuse_suite_results": {"per_task": abuse, "mean": abuse_mean},
            "online_sample_grades": {"status": "not_collected_offline"},
            "failure_analysis_log": failures,
        },
    )
