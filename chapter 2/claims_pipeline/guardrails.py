from __future__ import annotations

import json
import re
from typing import Any

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper

from .models import ClaimVerdict, TopicCheck

CLAIM_ID_PATTERN = re.compile(r"CLM-\d{4}")


def _coerce_input_text(raw_input: str | list[dict[str, Any]]) -> str:
    if isinstance(raw_input, str):
        return raw_input
    return json.dumps(raw_input)


def is_claim_related(text: str) -> bool:
    lowered = text.lower()
    return "claim" in lowered and (
        "policy" in lowered or CLAIM_ID_PATTERN.search(text) is not None
    )


def validate_claim_verdict(verdict: ClaimVerdict) -> tuple[bool, str]:
    if not verdict.cited_sections:
        return False, "The verdict must cite at least one policy section."
    if verdict.confidence < 0.0 or verdict.confidence > 1.0:
        return False, "The confidence score must be between 0.0 and 1.0."
    return True, "The verdict passed output validation."


def check_topic_relevance(
    run_context: RunContextWrapper[None],
    agent: Agent[Any],
    input_value: str | list[dict[str, Any]],
) -> GuardrailFunctionOutput:
    del run_context
    del agent
    text = _coerce_input_text(input_value)
    topic_check = TopicCheck(is_relevant=is_claim_related(text))
    return GuardrailFunctionOutput(
        output_info=topic_check,
        tripwire_triggered=not topic_check.is_relevant,
    )


def require_citations_and_valid_confidence(
    run_context: RunContextWrapper[None],
    agent: Agent[Any],
    output: Any,
) -> GuardrailFunctionOutput:
    del run_context
    del agent
    if not isinstance(output, ClaimVerdict):
        return GuardrailFunctionOutput(
            output_info="Unexpected output type.",
            tripwire_triggered=True,
        )
    is_valid, message = validate_claim_verdict(output)
    return GuardrailFunctionOutput(
        output_info=message,
        tripwire_triggered=not is_valid,
    )
