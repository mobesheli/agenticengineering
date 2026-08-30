"""Central model role for the optional live read phase."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistry:
    reader: str = "gpt-5-mini"


MODELS = ModelRegistry()
