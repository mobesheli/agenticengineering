"""Central model roles for the live performer and semantic judge."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistry:
    performer: str = "gpt-5-mini"
    judge: str = "gpt-5"


MODELS = ModelRegistry()
