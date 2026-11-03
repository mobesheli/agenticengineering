"""The triage agent handing off to a specialist, with tool history filtered."""

import asyncio

from agents import RunConfig, Runner
from agents.extensions import handoff_filters

from claims_pipeline.agents import triage_agent

config = RunConfig(
    handoff_input_filter=handoff_filters.remove_all_tools,
)


async def main() -> None:
    result = await Runner.run(
        triage_agent,
        "Does my HO-2024822 policy cover wind damage to a detached garage?",
        run_config=config,
    )
    print(f"answered by: {result.last_agent.name}")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
