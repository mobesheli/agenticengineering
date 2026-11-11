"""Every model name used in this chapter lives here.

Nothing in the agent code names a model directly. When the lineup changes,
this is the only file that changes.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistry:
    fast: str = "gpt-6-luna"
    mid: str = "gpt-6.1-terra"


MODELS = ModelRegistry()
