from __future__ import annotations

import pytest

from chapter7.dataset import load_tasks
from chapter7.gates import gate
from chapter7.graders import grade_suite
from chapter7.metrics import (
    build_suite_result,
    suite_score,
    task_reliability,
    theoretical_pass_at_k,
    theoretical_pass_to_k,
)
from chapter7.models import SuiteResult, TrialGrade
from chapter7.runner import run_suite


def result(**updates: float) -> SuiteResult:
    values = {
        "run_id": "baseline",
        "trial_count": 252,
        "task_count": 63,
        "k": 4,
        "quality_mean": 0.90,
        "quality_se": 0.02,
        "golden_pass_rate": 0.90,
        "abuse_pass_rate": 1.0,
        "pass_at_k": 0.98,
        "pass_to_k": 0.90,
        "cost_per_task": 0.10,
        "latency_p50": 2.0,
        "latency_p95": 4.0,
    }
    values.update(updates)
    return SuiteResult(**values)


def test_pass_at_k_and_pass_to_k_diverge_at_ninety_percent() -> None:
    assert theoretical_pass_at_k(0.9, 4) == pytest.approx(0.9999)
    assert theoretical_pass_to_k(0.9, 4) == pytest.approx(0.6561)


def test_observed_pass_to_k_requires_every_trial_to_pass() -> None:
    grades = [
        TrialGrade(task_id="task-a", index=index, passed=passed)
        for index, passed in enumerate([True, True, False, True])
    ]
    pass_at, pass_to = task_reliability(grades)
    assert pass_at == {"task-a": 1.0}
    assert pass_to == {"task-a": 0.0}


def test_suite_score_attaches_a_binomial_standard_error() -> None:
    mean, standard_error = suite_score({str(i): float(i < 8) for i in range(10)})
    assert mean == pytest.approx(0.8)
    assert standard_error == pytest.approx((0.8 * 0.2 / 10) ** 0.5)


def test_abuse_regression_is_a_hard_gate() -> None:
    verdict = gate(result(abuse_pass_rate=0.95), result())
    assert verdict.status == "block"
    assert verdict.reasons[0] == "abuse suite regressed"


def test_quality_blocks_only_after_the_combined_noise_margin() -> None:
    assert gate(result(quality_mean=0.84), result()).status == "block"
    assert gate(result(quality_mean=0.88), result()).status == "ok"


def test_cost_drift_warns_without_blocking() -> None:
    verdict = gate(result(cost_per_task=0.126), result())
    assert verdict.status == "warn"
    assert verdict.allows_deployment


@pytest.mark.asyncio
async def test_full_suite_aggregation_reports_all_four_headline_dimensions() -> None:
    tasks = load_tasks()
    trials = await run_suite(tasks, k=2)
    summary = build_suite_result(trials, grade_suite(tasks, trials))
    assert summary.task_count == 63
    assert summary.k == 2
    assert summary.golden_pass_rate == 1.0
    assert summary.abuse_pass_rate == 1.0
    assert summary.cost_per_task > 0
    assert summary.latency_p95 >= summary.latency_p50
