"""Every model name and reasoning setting used in this chapter lives here.

Agents refer to a role, such as ``MODELS.small``. This module maps each role to
the identifier the provider publishes. When the lineup changes, this is the
only file that changes.
"""

from dataclasses import dataclass

from agents import ModelSettings
from openai.types.shared import Reasoning


@dataclass(frozen=True)
class ModelRegistry:
    small: str = "gpt-6-luna"
    mid: str = "gpt-6.1-terra"
    frontier: str = "gpt-6.2-sol"
    frontier_canary: str = "gpt-6.2-astra"


MODELS = ModelRegistry()
QUICK = ModelSettings(reasoning=Reasoning(effort="low"))
DEEP = ModelSettings(reasoning=Reasoning(effort="high"))
