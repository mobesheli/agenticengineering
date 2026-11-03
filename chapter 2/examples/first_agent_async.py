"""The same agent run asynchronously with Runner.run and a turn budget.

Keep this in a separate process from Runner.run_sync: the SDK's shared
asynchronous client binds to the first event loop it meets.
"""

import asyncio

from agents import Runner

from examples.first_agent import CLAIM_TEXT, claims_reviewer


async def review_claim(claim_text: str) -> str:
    result = await Runner.run(
        claims_reviewer,
        claim_text,
        max_turns=10,
    )
    return result.final_output


if __name__ == "__main__":
    print(asyncio.run(review_claim(CLAIM_TEXT)))
