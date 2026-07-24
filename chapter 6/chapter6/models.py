"""Central model registry for the Chapter 6 examples.

The values intentionally continue the model tiers introduced in Chapter 5.
Keeping them here makes an upgrade or rollback a registry change rather than a
search-and-replace through orchestration code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistry:
    small: str = "gpt-5-nano"
    mid: str = "gpt-5-mini"
    frontier: str = "gpt-5"


MODELS = ModelRegistry()
