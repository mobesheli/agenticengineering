from __future__ import annotations

import json
import shutil

from chapter10.artifacts import TEMPLATE_ROOT
from chapter10.gate import compare_reports, run_pipeline, scan_secrets
from chapter10.models import EvaluationReport


def report(*, passed: int, bundle: str, cached: bool = False) -> EvaluationReport:
    return EvaluationReport(
        suite="golden@test",
        bundle=bundle,
        passed=passed,
        total=100,
        floor=0.85,
        trials_per_case=5,
        required_case_trials_passed=5,
        cache_enabled=cached,
        tokens=1000,
    )


def test_candidate_above_baseline_passes() -> None:
    decision = compare_reports(
        report(passed=99, bundle="candidate@2"),
        report(passed=82, bundle="baseline@1"),
        mode="block",
    )
    assert decision.verdict == "pass"
    assert not decision.enforced


def test_bad_candidate_blocks_only_when_mode_is_block() -> None:
    candidate = report(passed=70, bundle="candidate@2")
    baseline = report(passed=95, bundle="baseline@1")
    assert compare_reports(candidate, baseline, mode="block").enforced
    monitor = compare_reports(candidate, baseline, mode="monitor")
    assert monitor.verdict == "block"
    assert not monitor.enforced


def test_cached_release_evaluation_is_refused() -> None:
    decision = compare_reports(
        report(passed=99, bundle="candidate@2", cached=True),
        report(passed=90, bundle="baseline@1"),
        mode="block",
    )
    assert decision.enforced
    assert any("cached" in reason for reason in decision.reasons)


def test_checked_in_pipeline_passes_and_writes_report(tmp_path) -> None:
    output = tmp_path / "pipeline-report.json"
    pipeline = run_pipeline(TEMPLATE_ROOT, output_path=output)
    assert pipeline.passed
    assert [stage.name for stage in pipeline.stages] == [
        "deterministic-floor",
        "tool-contracts",
        "evaluation-gate",
        "provenance",
    ]
    assert json.loads(output.read_text())["bundle"] == "maintenance-planner@41.3"


def test_pipeline_catches_provenance_mismatch(tmp_path) -> None:
    project = tmp_path / "template"
    shutil.copytree(TEMPLATE_ROOT, project)
    path = project / "provenance.yaml"
    path.write_text(path.read_text().replace("953c18", "0000000"), encoding="utf-8")
    pipeline = run_pipeline(project)
    assert not pipeline.passed
    assert not next(
        stage for stage in pipeline.stages if stage.name == "provenance"
    ).passed


def test_secret_floor_finds_embedded_credentials(tmp_path) -> None:
    (tmp_path / "settings.py").write_text(
        'OPENAI_API_KEY="not-a-real-but-still-forbidden-key"\n', encoding="utf-8"
    )
    findings = scan_secrets(tmp_path)
    assert findings == ["settings.py: assigned API key"]
