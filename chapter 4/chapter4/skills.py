"""Procedural memory: skills are folders, loaded by name, described in one line."""

from __future__ import annotations

from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"


def describe_skills() -> dict[str, str]:
    """The table of contents: one line per skill, cheap enough to always carry."""
    catalog = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        header = path.read_text().split("---")[1]
        fields = dict(
            line.split(":", 1) for line in header.strip().splitlines() if ":" in line
        )
        catalog[fields["name"].strip()] = fields["description"].strip()
    return catalog


def load_skill(name: str) -> str:
    """The chapter itself: the full instructions, read only when the skill is used."""
    return (SKILLS / name / "SKILL.md").read_text().split("---", 2)[2].strip()
