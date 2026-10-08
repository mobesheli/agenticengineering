"""File loading, canonical hashing, and evidence-manifest helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
CHAPTER_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = CHAPTER_ROOT / "template-repository"


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def load_model(path: Path, model_type: type[T]) -> T:
    return model_type.model_validate(load_yaml(path))


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(
    directory: Path, *, exclude: set[str] | None = None
) -> dict[str, str]:
    omitted = exclude or {"manifest.json"}
    return {
        str(path.relative_to(directory)): file_sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and str(path.relative_to(directory)) not in omitted
    }


def verify_manifest(directory: Path) -> bool:
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return all(
        (directory / relative).is_file()
        and file_sha256(directory / relative) == expected
        for relative, expected in manifest.items()
    )
