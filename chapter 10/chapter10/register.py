"""File-backed agent register and evidence-based listing gate."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from .artifacts import CHAPTER_ROOT, load_model, load_yaml
from .models import AgentEntry, EvaluationReport, ListingResult


class FileRepository:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("evidence path escapes the repository")
        return path

    def exists(self, relative: str) -> bool:
        return self.resolve(relative).is_file()

    def read_json(self, relative: str) -> dict:
        return json.loads(self.resolve(relative).read_text(encoding="utf-8"))


def load_requirements(path: Path) -> dict[str, list[str]]:
    payload = load_yaml(path)
    return {tier: list(fields) for tier, fields in payload.items()}


def listing_check(
    entry: AgentEntry,
    required: dict[str, list[str]],
    repo: FileRepository,
) -> ListingResult:
    missing: list[str] = []
    for evidence_name in required[entry.tier]:
        evidence_path = entry.evidence.get(evidence_name)
        if not evidence_path:
            missing.append(f"{evidence_name}: not declared")
        elif not repo.exists(evidence_path):
            missing.append(f"{evidence_name}: file not found")

    report_path = entry.evidence.get("eval_report")
    if report_path and repo.exists(report_path):
        report = EvaluationReport.model_validate(repo.read_json(report_path))
        if report.bundle != entry.bundle:
            missing.append("eval_report was produced under a different bundle")
        if report.pass_rate < report.floor:
            missing.append("eval_report is below its floor")
        if not report.required_pass_k:
            missing.append("eval_report failed a required pass^k case")
        if report.cache_enabled:
            missing.append("eval_report used cached answers")
    return ListingResult(agent=entry.agent, accepted=not missing, missing=missing)


def run_listing_demo(output_dir: Path) -> tuple[ListingResult, ListingResult]:
    """Refuse the seed entry, create its evidence, then accept the same entry."""

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    entry = load_model(
        CHAPTER_ROOT / "data/register/candidates/maintenance-planner.yaml",
        AgentEntry,
    )
    requirements = load_requirements(CHAPTER_ROOT / "data/register/requirements.yaml")
    repo = FileRepository(output_dir)
    refused = listing_check(entry, requirements, repo)

    bundle_target = repo.resolve(entry.evidence["config_ref"])
    bundle_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CHAPTER_ROOT / "template-repository/bundle.yaml", bundle_target)

    report_target = repo.resolve(entry.evidence["eval_report"])
    report_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        CHAPTER_ROOT / "template-repository/evals/candidate.json",
        report_target,
    )

    prose = {
        "tier_record": "High tier: creates maintenance work-order proposals for human approval.\n",
        "security_review": "Reviewed: scoped identity, contract hook, approval, and kill switches.\n",
        "oversight_note": "A named planner approves every work order before any effect.\n",
    }
    for evidence_name, content in prose.items():
        target = repo.resolve(entry.evidence[evidence_name])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    accepted = listing_check(entry, requirements, repo)
    listed_entry = entry.model_copy(update={"status": "listed"})
    (output_dir / "register-entry.yaml").write_text(
        yaml.safe_dump(listed_entry.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    (output_dir / "listing-results.json").write_text(
        json.dumps(
            {
                "first_attempt": refused.model_dump(mode="json"),
                "after_evidence": accepted.model_dump(mode="json"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return refused, accepted
