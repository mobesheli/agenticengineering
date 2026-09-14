from __future__ import annotations

from chapter9.anomalies import (
    credit_depletion_state,
    detector_coverage,
    robust_cost_anomalies,
)
from chapter9.maintenance import MaintenanceHarness
from chapter9.quality import (
    JudgeCalibrationMonitor,
    calibration_report,
    cohens_kappa,
    stable_human_review_sample,
)


def test_kappa_exposes_chance_agreement_hidden_by_raw_agreement() -> None:
    human = ["pass"] * 8 + ["fail"] * 2
    judge = ["pass"] * 10
    report = calibration_report(
        period="2026-08",
        judge_version="judge-v1",
        human_labels=human,
        judge_labels=judge,
    )
    assert report["raw_agreement"] == 0.8
    assert report["cohens_kappa"] == 0.0
    assert cohens_kappa(["pass", "fail"], ["pass", "fail"]) == 1.0


def test_monitor_recalibrates_on_kappa_drop_or_judge_change() -> None:
    monitor = JudgeCalibrationMonitor(minimum_kappa=0.5, maximum_drop=0.1)
    first = calibration_report(
        period="2026-07",
        judge_version="judge-v1",
        human_labels=["pass", "pass", "fail", "fail", "pass", "fail"],
        judge_labels=["pass", "pass", "fail", "fail", "pass", "pass"],
    )
    second = calibration_report(
        period="2026-08",
        judge_version="judge-v2",
        human_labels=["pass", "pass", "fail", "fail", "pass", "fail"],
        judge_labels=["pass", "pass", "pass", "pass", "pass", "pass"],
    )
    assert monitor.add(first)["status"] == "ok"
    verdict = monitor.add(second)
    assert verdict["status"] == "recalibrate"
    assert len(verdict["reasons"]) == 3


def test_human_review_sample_is_stable_and_unique() -> None:
    trace_ids = [f"trace-{index}" for index in range(20)]
    first = stable_human_review_sample(trace_ids, sample_size=5, seed=9)
    second = stable_human_review_sample(reversed(trace_ids), sample_size=5, seed=9)
    assert first == second
    assert len(set(first)) == 5


def test_credit_alerts_fire_at_half_and_a_fifth_remaining() -> None:
    assert credit_depletion_state(49, 100)["status"] == "ok"
    assert credit_depletion_state(50, 100)["status"] == "warn"
    assert credit_depletion_state(80, 100)["status"] == "page"
    assert credit_depletion_state(100, 100)["status"] == "exhausted"


def test_detector_coverage_makes_missing_plant_dimension_visible() -> None:
    report = detector_coverage(
        {"cloud": ["service", "account", "region"]},
        required_dimensions=["service", "account", "region", "plant", "principal"],
    )
    assert report["status"] == "gap"
    assert report["missing_dimensions"] == ["plant", "principal"]


def test_robust_anomaly_report_carries_owner_and_workload() -> None:
    traces = MaintenanceHarness().run_all()
    expensive = traces[0].model_copy(deep=True)
    expensive.trace_id = "trace-outlier"
    expensive.review_minutes = 100
    report = robust_cost_anomalies([*traces, expensive])
    outlier = next(row for row in report if row["trace_id"] == "trace-outlier")
    assert outlier["owner"] == "maintenance-platform-team"
    assert outlier["workload"] == "maintenance_planning"
