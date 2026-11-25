"""Model names and run identity. They live here and nowhere else in the code."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

MODELS = {"plan": "gpt-6.2-sol", "read": "gpt-6.1-terra", "draft": "gpt-6-luna"}
FRONTIER = MODELS["plan"]
WORKFLOW = "maintenance work order"
IDENTITY = {
    "tenant": "manufacturing",
    "agent_version": "40.6",
    "prompt_bundle": "maintenance@40",
    "tool_catalog": "plant-tools@7",
}
