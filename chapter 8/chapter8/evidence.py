"""Collect the security evidence pack: files, hashes, and the date it was built."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from chapter8.harness import Harness
from chapter8.settings import AGENT_VERSION, DATA, MODELS, ROOT


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bill_of_materials(harness: Harness) -> dict[str, Any]:
    pins = (ROOT / "requirements.txt").read_text().split()
    server = f"{harness.catalog.server}=={harness.catalog.version}"
    return {
        "agent": AGENT_VERSION,
        "models": MODELS,
        "packages": pins,
        "tool_servers": [server],
    }


def build_pack(
    harness: Harness, canary_report: dict[str, str], out: Path
) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    mark = harness.notary.checkpoint(harness.log)
    records = [
        record.model_dump(mode="json") for record in harness.log.records()
    ]
    agents = [
        entry.model_dump(mode="json")
        for entry in (
            harness.registry.entry("reconciliation-reader"),
            harness.registry.entry("reconciliation-writer"),
        )
        if entry
    ]
    written = {
        "01-agent-registry.json": agents,
        "04-decision-records.json": {
            "records": records,
            "checkpoint": mark.__dict__,
        },
        "05-redaction-canary-report.json": canary_report,
        "08-bill-of-materials.json": bill_of_materials(harness),
    }
    for name, content in written.items():
        (out / name).write_text(json.dumps(content, indent=2) + "\n")
    copied = {
        "02-tool-catalog.yaml": DATA / "catalog" / "ehr-records.yaml",
        "03-write-policy.yaml": DATA / "policies" / "write-policy.yaml",
        "06-retention.yaml": DATA / "policies" / "retention.yaml",
        "07-stop-drill.txt": ROOT / "outputs" / "stop_drill.txt",
    }
    for name, source in copied.items():
        (out / name).write_bytes(source.read_bytes())
    manifest = {
        "built_at": harness.clock().isoformat(),
        "files": {path.name: _digest(path) for path in sorted(out.iterdir())},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return [
        f"{name}  {digest[:12]}" for name, digest in manifest["files"].items()
    ]
