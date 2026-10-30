"""Small, portable file helpers for fixtures and evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHAPTER_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = CHAPTER_ROOT / "data"


def load_json(name: str):
    return json.loads((DATA_ROOT / name).read_text(encoding="utf-8"))


def digest(value) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def build_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != root / "manifest.json"
    }


def verify_manifest(root: Path) -> bool:
    """Check the entire file set, including additions, removals, and unsafe paths."""
    try:
        root = root.resolve()
        expected = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(expected, dict) or not expected:
            return False
        for name in expected:
            path = root / name
            if not path.resolve().is_relative_to(root) or path.is_symlink():
                return False
        return expected == build_manifest(root)
    except (OSError, ValueError, TypeError):
        return False
