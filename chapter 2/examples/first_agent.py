"""The simplest agent in the chapter, run synchronously and asynchronously."""

import asyncio

from agents import Agent, Runner

from claims_pipeline.settings import MODELS

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=(
        "You are a senior insurance claims reviewer. "
        "Analyze submitted claims for completeness, "
        "flag missing documentation, and assess whether "
        "the claim falls within standard policy coverage. "
        "Always cite the specific policy section that "
        "applies to your determination."
    ),
)

CLAIM_TEXT = (
    "Claim #4821: Water damage to basement. "
    "Policy: HO-3. Date of loss: 2026-01-15. "
    "Submitted documents: photos, contractor estimate."
)


async def review_claim(claim_text: str) -> str:
    result = await Runner.run(
        claims_reviewer,
        claim_text,
        max_turns=10,
    )
    return result.final_output


if __name__ == "__main__":
    sync_result = Runner.run_sync(claims_reviewer, CLAIM_TEXT)
    print(sync_result.final_output)
    print("---")
    print(asyncio.run(review_claim(CLAIM_TEXT)))
