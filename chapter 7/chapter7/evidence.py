"""Package one suite run as a model-risk evidence folder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import SuiteResult

SR_11_7_MAP = {
    "golden_suite_results": "conceptual_soundness_testing",
    "abuse_suite_results": "effective_challenge",
    "online_sample_grades": "ongoing_monitoring",
    "failure_analysis_log": "documented_limitations",
}


def _write_json(path: Path, payload: Any) -> str:
    content = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def emit_evidence_pack(run: SuiteResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []
    for artifact, control in SR_11_7_MAP.items():
        path = out_dir / f"{control}__{artifact}.json"
        digest = _write_json(path, run.artifacts.get(artifact, {}))
        records.append(
            {
                "artifact": artifact,
                "control": control,
                "path": path.name,
                "sha256": digest,
            }
        )
    manifest = out_dir / "manifest.json"
    _write_json(manifest, {"run_id": run.run_id, "records": records})
    return manifest
