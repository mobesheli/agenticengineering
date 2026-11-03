"""Input and output guardrails for the claims pipeline."""

from typing import Any

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, Runner

from .models import ClaimVerdict, TopicCheck
from .settings import MODELS

topic_classifier = Agent(
    name="topic_classifier",
    model=MODELS.fast,
    instructions=(
        "Decide whether the text is an insurance claim or a question "
        "about an insurance policy. Set is_relevant to true only for "
        "insurance claims and policy matters. Give a one-sentence reason."
    ),
    output_type=TopicCheck,
)


async def reject_non_insurance(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    input_text: Any,
) -> GuardrailFunctionOutput:
    result = await Runner.run(
        topic_classifier,
        input_text,
        context=ctx.context,
    )
    check: TopicCheck = result.final_output
    return GuardrailFunctionOutput(
        output_info=check,
        tripwire_triggered=not check.is_relevant,
    )


async def enforce_citations(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    output: ClaimVerdict,
) -> GuardrailFunctionOutput:
    decided = output.decision in ("approve", "deny")
    has_citations = len(output.cited_sections) > 0
    return GuardrailFunctionOutput(
        output_info={"decision": output.decision, "citations": len(output.cited_sections)},
        tripwire_triggered=decided and not has_citations,
    )
