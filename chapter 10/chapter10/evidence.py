"""Generate and verify the offline Chapter 10 release evidence pack."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .artifacts import TEMPLATE_ROOT, build_manifest, verify_manifest
from .board import write_board
from .gate import run_pipeline
from .models import GateMode
from .register import run_listing_demo
from .switches import KillSwitchMap


def emit_deployment_evidence(
    output_dir: Path,
    *,
    mode: GateMode = "block",
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = run_pipeline(
        TEMPLATE_ROOT,
        mode=mode,
        output_path=output_dir / "pipeline-report.json",
    )
    refused, accepted = run_listing_demo(output_dir / "listing-demo")
    board = write_board(output_dir / "agent-board.json")
    drills = [
        result.model_dump(mode="json")
        for result in KillSwitchMap("maintenance-planner").drill_all()
    ]
    (output_dir / "kill-switch-drill.json").write_text(
        json.dumps(drills, indent=2), encoding="utf-8"
    )
    shutil.copy2(TEMPLATE_ROOT / "bundle.yaml", output_dir / "bundle.yaml")
    manifest = build_manifest(output_dir)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {
        "pipeline_passed": pipeline.passed,
        "listing_first_attempt": refused.accepted,
        "listing_after_evidence": accepted.accepted,
        "agents_on_board": len(board),
        "kill_switches_drilled": len(drills),
        "manifest_verified": verify_manifest(output_dir),
    }


__all__ = ["emit_deployment_evidence", "verify_manifest"]
