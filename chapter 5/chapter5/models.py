"""Central model registry used by the Chapter 5 examples.

The model names are illustrative dated snapshots. In a production codebase,
this is the one file you would review when upgrading or rolling back models.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistry:
    small: str = "gpt-5.4-nano-2026-03-05"
    mid: str = "gpt-5.4-mini-2026-03-05"
    frontier: str = "gpt-5.4-2026-03-05"
    frontier_canary: str = "gpt-5.5-2026-05-12"


MODELS = ModelRegistry()
