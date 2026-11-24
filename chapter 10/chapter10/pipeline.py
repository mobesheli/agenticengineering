"""The release pipeline, runnable on a laptop: floor, bundle, contracts, gate, record.

python -m chapter10.pipeline --repo template-repository --mode block
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

from chapter10.bundle import broken_references, bundle_digest, load_bundle
from chapter10.contracts import contract_problems, load_contracts
from chapter10.gate import Decision, EvalResult, Mode, decide, enforce

SECRETS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "provider key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
}
TEXT_FILES = {".py", ".yaml", ".yml", ".json", ".md", ".txt", ".toml", ".env", ""}


class Stage(BaseModel):
    name: str
    passed: bool
    detail: str


class PipelineReport(BaseModel):
    bundle: str
    bundle_digest: str
    mode: Mode
    stages: list[Stage]
    decision: Decision
    exit_code: int


def scan_for_secrets(repo: Path) -> list[str]:
    found = []
    for path in sorted(p for p in repo.rglob("*") if p.is_file()):
        if path.suffix not in TEXT_FILES or "results" in path.parts:
            continue
        content = path.read_text(errors="ignore")
        found += [
            f"{path.relative_to(repo)}: {label}"
            for label, pattern in SECRETS.items()
            if pattern.search(content)
        ]
    return found


def load_result(path: Path) -> EvalResult:
    return EvalResult.model_validate(json.loads(path.read_text()))


def run_pipeline(
    repo: Path,
    mode: Mode,
    candidate: str = "evals/candidate.json",
    out: Path | None = None,
) -> PipelineReport:
    bundle = load_bundle(repo)
    policy = yaml.safe_load((repo / "policies" / "release.yaml").read_text())
    secrets = scan_for_secrets(repo)
    references = broken_references(bundle, repo)
    contracts = contract_problems(load_contracts(repo / "contracts"))
    stages = [
        Stage(
            name="floor", passed=not secrets, detail="; ".join(secrets) or "no secrets"
        ),
        Stage(
            name="bundle",
            passed=not references,
            detail="; ".join(references) or "every pointer matches its file",
        ),
        Stage(
            name="contracts",
            passed=not contracts,
            detail="; ".join(contracts) or "agent identity, egress declared",
        ),
    ]
    result = load_result(repo / candidate)
    decision = decide(
        load_result(repo / "evals" / "baseline.json"),
        result,
        floor=policy["gate"]["floor"],
        release=True,
    )
    if result.bundle != bundle.bundle or result.suite != bundle.eval_suite:
        decision = Decision("block", "the report is for another release")
    gate_exit, effect = enforce(decision, mode)
    detail = f"{decision.verdict}: {decision.reason} ({effect})"
    stages.append(Stage(name="gate", passed=gate_exit == 0, detail=detail))
    mandatory_failed = not all(stage.passed for stage in stages[:3])
    report = PipelineReport(
        bundle=bundle.bundle,
        bundle_digest=bundle_digest(bundle),
        mode=mode,
        stages=stages,
        decision=decision,
        exit_code=1 if mandatory_failed else gate_exit,
    )
    if out is not None and report.exit_code == 0 and decision.verdict != "block":
        write_release_record(repo, candidate, report, out)
    return report


def write_release_record(
    repo: Path, candidate: str, report: PipelineReport, out: Path
) -> Path:
    """What the pipeline certifies: this report, for this bundle, with this hash."""
    out.mkdir(parents=True, exist_ok=True)
    report_bytes = (repo / candidate).read_bytes()
    (out / "eval-report.json").write_bytes(report_bytes)
    record = {
        "bundle": report.bundle,
        "bundle_digest": report.bundle_digest,
        "suite": load_bundle(repo).eval_suite,
        "verdict": report.decision.verdict,
        "eval_report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "produced_by": "release-pipeline",
    }
    path = out / "release-record.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path


def render(report: PipelineReport) -> list[str]:
    lines = [f"bundle {report.bundle}  digest {report.bundle_digest[:12]}"]
    for stage in report.stages:
        lines.append(
            f"  {stage.name:11}{'ok' if stage.passed else 'STOP':6}{stage.detail}"
        )
    lines.append(f"  exit code {report.exit_code}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the release pipeline locally.")
    parser.add_argument("--repo", type=Path, default=Path("template-repository"))
    parser.add_argument(
        "--mode", choices=["monitor", "comment", "block"], default="block"
    )
    parser.add_argument("--candidate", default="evals/candidate.json")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run_pipeline(args.repo, args.mode, args.candidate, args.out)
    print("\n".join(render(report)))
    sys.exit(report.exit_code)


if __name__ == "__main__":
    main()
