"""A local release pipeline with deterministic checks and an evaluation gate."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import load_model, load_yaml
from .contracts import ContractEnforcer
from .models import (
    EvaluationReport,
    GateDecision,
    GateMode,
    PipelineReport,
    PipelineStage,
)
from .release import bundle_digest, load_bundle

SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "provider key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "assigned API key": re.compile(r"OPENAI_API_KEY\s*=\s*['\"]?[^$\s'\"]+"),
    "bearer token": re.compile(
        r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE
    ),
}


def wilson_interval(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    proportion = passed / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((proportion * (1 - proportion) + z**2 / (4 * total)) / total)
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def compare_reports(
    candidate: EvaluationReport,
    baseline: EvaluationReport,
    *,
    mode: GateMode,
) -> GateDecision:
    candidate_interval = wilson_interval(candidate.passed, candidate.total)
    baseline_interval = wilson_interval(baseline.passed, baseline.total)
    reasons: list[str] = []
    verdict = "pass"
    if candidate.bundle == baseline.bundle:
        reasons.append("candidate and baseline must name different bundles")
        verdict = "block"
    if candidate.cache_enabled:
        reasons.append("release certification cannot use cached model answers")
        verdict = "block"
    if candidate.pass_rate < candidate.floor:
        reasons.append("candidate is below its declared quality floor")
        verdict = "block"
    if not candidate.required_pass_k:
        reasons.append("a required case did not pass every trial")
        verdict = "block"
    if candidate_interval[1] < baseline_interval[0]:
        reasons.append("candidate interval is entirely below the baseline interval")
        verdict = "block"
    elif candidate_interval[0] <= baseline_interval[1] and verdict == "pass":
        reasons.append("candidate and baseline intervals overlap")
        verdict = "warn"
    if not reasons:
        reasons.append("candidate clears its floor and the baseline interval")
    return GateDecision(
        mode=mode,
        verdict=verdict,
        enforced=mode == "block" and verdict == "block",
        candidate_rate=candidate.pass_rate,
        baseline_rate=baseline.pass_rate,
        candidate_interval=candidate_interval,
        baseline_interval=baseline_interval,
        reasons=reasons,
    )


def scan_secrets(root: Path) -> list[str]:
    findings: list[str] = []
    allowed_suffixes = {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".toml"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        if any(part in {".git", ".venv", "artifacts"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(root)}: {label}")
    return findings


def run_pipeline(
    project_root: Path,
    *,
    mode: GateMode = "block",
    output_path: Path | None = None,
) -> PipelineReport:
    bundle = load_bundle(project_root / "bundle.yaml")
    digest = bundle_digest(bundle)
    stages: list[PipelineStage] = []

    findings = scan_secrets(project_root)
    stages.append(
        PipelineStage(
            name="deterministic-floor",
            passed=not findings,
            detail="no embedded secrets found" if not findings else "; ".join(findings),
        )
    )

    ContractEnforcer.from_directory(project_root / "contracts")
    stages.append(
        PipelineStage(
            name="tool-contracts",
            passed=True,
            detail="contracts parse, scopes are disjoint, and workload identity is required",
        )
    )

    baseline = load_model(project_root / "evals" / "baseline.json", EvaluationReport)
    candidate = load_model(project_root / "evals" / "candidate.json", EvaluationReport)
    bundle_matches = candidate.bundle == bundle.bundle
    gate = compare_reports(candidate, baseline, mode=mode)
    gate_passed = bundle_matches and not gate.enforced
    gate_detail = "; ".join(gate.reasons)
    if not bundle_matches:
        gate_detail = (
            "evaluation report was produced under a different bundle; " + gate_detail
        )
    stages.append(
        PipelineStage(name="evaluation-gate", passed=gate_passed, detail=gate_detail)
    )

    provenance = load_yaml(project_root / "provenance.yaml")
    expected_subject = provenance.get("subject", {}).get("digest")
    provenance_ok = expected_subject == f"sha256:{digest}"
    stages.append(
        PipelineStage(
            name="provenance",
            passed=provenance_ok,
            detail=(
                "bundle digest matches signed-build subject"
                if provenance_ok
                else "provenance subject does not match the release bundle"
            ),
        )
    )

    report = PipelineReport(
        bundle=bundle.bundle,
        bundle_digest=digest,
        mode=mode,
        passed=all(stage.passed for stage in stages),
        stages=stages,
        gate=gate,
        created_at=datetime.now(timezone.utc),
    )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def load_pipeline_report(path: Path) -> PipelineReport:
    return PipelineReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
