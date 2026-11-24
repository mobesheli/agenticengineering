"""The release bundle: one file that names everything that changes behavior."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template-repository"


class ModelPin(BaseModel):
    id: str
    effort: str
    golden: str | None = None


class Bundle(BaseModel):
    bundle: str
    image: str
    sandbox: str
    prompts: str
    contracts: dict[str, str]
    policy_pack: str
    model: dict[str, ModelPin]
    memory_schema: dict[str, Any]
    eval_suite: str


def load_bundle(repo: Path = TEMPLATE) -> Bundle:
    return Bundle.model_validate(yaml.safe_load((repo / "bundle.yaml").read_text()))


def bundle_digest(bundle: Bundle) -> str:
    canonical = json.dumps(bundle.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def file_digest(path: Path, length: int = 12) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:length]


def broken_references(bundle: Bundle, repo: Path = TEMPLATE) -> list[str]:
    """Every pointer in the bundle that does not match the file it names."""
    problems = []
    prompt_file, _, pinned = bundle.prompts.partition("@")
    if not (repo / prompt_file).exists():
        problems.append(f"{prompt_file} is missing")
    elif file_digest(repo / prompt_file) != pinned:
        problems.append(f"{prompt_file} changed since the bundle was written")
    for name, version in bundle.contracts.items():
        path = repo / "contracts" / f"{name}.yaml"
        found = yaml.safe_load(path.read_text())["version"] if path.exists() else None
        if found != version:
            problems.append(
                f"contract {name}: bundle says {version}, file says {found}"
            )
    golden = bundle.model["fallback"].golden
    if not golden or not (repo / golden).exists():
        problems.append("the fallback model has no golden-suite result")
    return problems
