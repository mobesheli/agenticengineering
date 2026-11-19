"""A conversation that survives between turns, because a session carries it.

python -m examples.billing_session              # needs OPENAI_API_KEY
python -m examples.billing_session --scripted   # no key: scripted model
"""

from __future__ import annotations

import asyncio
import sys

from agents import Agent, Runner, SQLiteSession
from agents.models.interface import Model

from chapter4.models import MODELS


async def main(
    model: str | Model = MODELS.mid, db_path: str = "conversations.db"
) -> str:
    agent = Agent(
        name="billing-support",
        model=model,
        instructions="You help customers with billing questions. Be concise.",
    )

    session = SQLiteSession(session_id="customer-4837", db_path=db_path)

    await Runner.run(agent, "I was double charged in March.", session=session)
    reply = await Runner.run(agent, "I got cut off. Where were we?", session=session)
    return reply.final_output


if __name__ == "__main__":
    if "--scripted" in sys.argv:
        from examples.scripted import scripted_billing_model

        print(asyncio.run(main(scripted_billing_model(), ":memory:")))
    else:
        print(asyncio.run(main()))
