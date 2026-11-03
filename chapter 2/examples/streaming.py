"""Streaming the reviewer's output token by token."""

import asyncio

from agents import Runner

from examples.first_agent import CLAIM_TEXT, claims_reviewer


async def stream_review(claim_text: str) -> None:
    result = Runner.run_streamed(
        claims_reviewer, claim_text
    )
    async for event in result.stream_events():
        if event.type == "raw_response_event":
            if hasattr(event.data, "delta"):
                print(event.data.delta, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(stream_review(CLAIM_TEXT))
