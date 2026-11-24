"""Model names and run limits. They live here and nowhere else in the code."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MODELS = {"reader": "gpt-6.1-terra", "writer": "gpt-6-luna"}
READER_TURNS = 10
WRITER_TURNS = 4
AGENT_VERSION = "8.2.0"
FIXED_NOW = datetime(2027, 3, 2, 9, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    """The clock the examples use, so that their output is the same on every run."""
    return FIXED_NOW
