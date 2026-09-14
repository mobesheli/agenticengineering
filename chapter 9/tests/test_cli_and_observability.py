from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from chapter9.maintenance import MaintenanceHarness
from chapter9.telemetry import _attributes

ROOT = Path(__file__).resolve().parents[1]


def test_cli_runs_offline_and_emits_verified_artifacts(tmp_path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "chapter9", "--output-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["trace_count"] == 24
    assert payload["manifest_verified"] is True
    assert (tmp_path / "value_review.html").exists()


def test_otlp_attributes_carry_identity_price_and_outcome() -> None:
    trace = MaintenanceHarness().run_all()[-1]
    attrs = _attributes(trace)
    assert attrs["chapter9.trace_id"] == trace.trace_id
    assert attrs["chapter9.plant"] == "Plant D"
    assert attrs["chapter9.cost_usd"] == trace.fully_loaded_cost_usd
    assert attrs["chapter9.outcome"] == trace.outcome


def test_one_container_stack_exposes_grafana_and_both_otlp_ports() -> None:
    compose = (ROOT / "compose.yaml").read_text()
    assert "grafana/otel-lgtm" in compose
    assert '"3000:3000"' in compose
    assert '"4317:4317"' in compose
    assert '"4318:4318"' in compose
