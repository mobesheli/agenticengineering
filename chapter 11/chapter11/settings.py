"""Where the data lives, and the one agent the chapter follows for a year."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AGENT = "maintenance-planner"
WORKFLOW = "maintenance work order"


def load(name: str) -> Any:
    return yaml.safe_load((DATA / f"{name}.yaml").read_text())
