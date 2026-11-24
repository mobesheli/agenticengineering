"""The register: one entry for every agent the company runs, built or bought."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from chapter10.gate import EvalResult

DATA = Path(__file__).resolve().parents[1] / "data"
RECORDS = DATA / "records"

LADDERS = {
    "build": [
        "registered",
        "identified",
        "connected",
        "gated",
        "live",
        "listed",
        "steady",
    ],
    "join": ["registered", "connected", "fixed", "gated", "listed", "steady"],
    "assemble": [
        "intake",
        "scaffolded",
        "golden set",
        "gated",
        "live",
        "listed",
        "steady",
    ],
    "buy": ["named", "assessed", "contracted", "accepted", "listed", "steady"],
}


class Entry(BaseModel):
    agent: str
    owner: str
    route: str
    tier: str
    status: str
    bundle: str
    budget: dict[str, Any]
    evidence: dict[str, str]
    data_sources: list[str] = []
    value_line: dict[str, str]
    monitoring: str | None = None


def load_entry(path: Path) -> Entry:
    return Entry.model_validate(yaml.safe_load(path.read_text()))


def load_register(folder: Path = DATA / "register") -> list[Entry]:
    return [load_entry(path) for path in sorted(folder.glob("*.yaml"))]


def required_evidence(tier: str) -> list[str]:
    policy = yaml.safe_load((DATA / "requirements.yaml").read_text())
    return policy[tier]


def listing_check(entry: Entry, required: list[str], repo: Path) -> list[str]:
    files = {name: repo / path for name, path in entry.evidence.items()}
    present = {name for name, path in files.items() if path.is_file()}
    missing = [name for name in required if name not in present]
    if missing:
        return [f"missing evidence: {name}" for name in missing]
    try:
        report_bytes = files["eval_report"].read_bytes()
        record = json.loads(files["release_record"].read_text())
        report = EvalResult.model_validate_json(report_bytes)
        certified, verdict = record["eval_report_sha256"], record["verdict"]
    except (ValueError, KeyError) as error:
        return [f"evidence cannot be read: {type(error).__name__}"]
    problems = []
    if certified != hashlib.sha256(report_bytes).hexdigest():
        problems.append("eval_report is not the file the pipeline certified")
    if report.bundle != entry.bundle or record["bundle"] != entry.bundle:
        problems.append("eval_report was produced under a different bundle")
    if verdict == "block":
        problems.append("the release gate blocked this bundle")
    return problems


def find_unregistered(entries: list[Entry], inventory: dict[str, Any]) -> list[str]:
    """Compare the register with the systems an agent cannot avoid touching."""
    known = {entry.agent for entry in entries}
    findings = []
    for source in (
        "gateway_keys",
        "identities",
        "provider_invoices",
        "vendor_features",
    ):
        for item in inventory.get(source, []):
            if item["agent"] not in known:
                label = source.replace("_", " ").rstrip("s")
                findings.append(f"{label} '{item['name']}' has no register entry")
    return findings
