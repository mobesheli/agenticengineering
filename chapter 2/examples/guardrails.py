"""The blocking input guardrail rejecting a request that is not an insurance matter."""

import asyncio

from agents import Runner
from agents.exceptions import InputGuardrailTripwireTriggered

from claims_pipeline.agents import intake_agent
from claims_pipeline.data import OFF_TOPIC_REQUEST, SAMPLE_CLAIMS


async def main() -> None:
    print("input guardrails:", [g.name for g in intake_agent.input_guardrails])
    try:
        await Runner.run(intake_agent, OFF_TOPIC_REQUEST)
        print("not rejected")
    except InputGuardrailTripwireTriggered as exc:
        print("rejected:", exc.guardrail_result.output.output_info)
    result = await Runner.run(intake_agent, SAMPLE_CLAIMS["CLM-4821"].as_text())
    print("accepted:", result.final_output.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
