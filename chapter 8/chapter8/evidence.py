"""Security review evidence and manifest generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .identity import clinician_read_session
from .models import SecurityOutcome
from .registry import AgentStoppedError
from .runtime import SecurityHarness


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit_security_evidence(
    harness: SecurityHarness,
    outcome: SecurityOutcome,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "agent_registry.json": harness.registry.snapshot(),
        "tool_catalog.json": harness.catalog.model_dump(mode="json"),
        "policy_bundle.json": harness.policy_config,
        "decision_records.json": [
            {
                **record.model_dump(mode="json"),
                "content_hash": record.content_hash(),
            }
            for record in harness.decisions.records
        ],
        "fhir_audit_events.json": harness.fhir_audit_events,
        "privacy_canary.json": harness.privacy_canary_report(),
        "run_outcome.json": outcome.model_dump(mode="json"),
    }
    for name, payload in artifacts.items():
        _write_json(output_dir / name, payload)

    patient_id = outcome.patient_id
    clinician_ref = harness.decisions.records[-1].principal
    harness.stop("scheduled stop-control test")
    stopped = False
    reason = ""
    try:
        session = clinician_read_session(
            clinician_ref=clinician_ref,
            patient_id=patient_id,
            now=harness.clock(),
        )
        harness.propose(session)
    except AgentStoppedError as exc:
        stopped = True
        reason = str(exc)
    finally:
        harness.registry.restore(harness.agent_id)
    stop_path = output_dir / "stop_control.json"
    _write_json(stop_path, {"passed": stopped, "observed_reason": reason})

    manifest_entries = {
        path.name: _file_hash(path)
        for path in sorted(output_dir.glob("*.json"))
        if path.name != "manifest.json"
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(
        manifest_path,
        {
            "manifest_version": 1,
            "chain_verified": harness.decisions.verify(),
            "artifacts": manifest_entries,
        },
    )
    return manifest_path


def verify_manifest(manifest_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return bool(manifest.get("chain_verified")) and all(
        _file_hash(manifest_path.parent / name) == expected
        for name, expected in manifest["artifacts"].items()
    )
