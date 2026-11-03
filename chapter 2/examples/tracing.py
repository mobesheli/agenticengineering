"""Grouping two runs under one trace, with a valid trace ID and business metadata."""

import asyncio

from agents import RunConfig, Runner, trace
from agents.tracing import gen_trace_id

from claims_pipeline.agents import claims_reviewer, triage_agent
from claims_pipeline.data import SAMPLE_CLAIMS

config = RunConfig(
    workflow_name="claims_processing",
    trace_id=gen_trace_id(),
    group_id="batch-daily-claims",
    trace_metadata={"claim_ref": "CLM-4821"},
    trace_include_sensitive_data=False,
)


async def process_claim_workflow(claim_text: str):
    with trace("claims_workflow", trace_id=gen_trace_id()):
        triage_result = await Runner.run(
            triage_agent, claim_text
        )
        review_result = await Runner.run(
            claims_reviewer,
            f"Review: {triage_result.final_output}",
        )
    return review_result


async def main() -> None:
    claim = SAMPLE_CLAIMS["CLM-4821"]
    configured = await Runner.run(claims_reviewer, claim.as_text(), run_config=config)
    print(configured.final_output.model_dump_json(indent=2))
    grouped = await process_claim_workflow(claim.as_text())
    print(grouped.final_output.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
