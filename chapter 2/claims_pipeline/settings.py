"""Every model name and business threshold used by the pipeline lives here.

Nothing in the agent code names a model directly. When the model lineup
changes, this is the only file that needs to change.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRegistry:
    fast: str = "gpt-6-luna"
    review: str = "gpt-6.1-terra"


MODELS = ModelRegistry()

ESCALATION_CONFIDENCE = 0.90
ESCALATION_AMOUNT_USD = 50_000.0
MAX_HISTORY_YEARS = 5
TOOL_TIMEOUT_SECONDS = 30
INTAKE_MAX_TURNS = 5
REVIEW_MAX_TURNS = 10
