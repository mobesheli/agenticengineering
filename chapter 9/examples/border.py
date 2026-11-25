"""A call to a supplier's agent, recorded on your side of the border.

python -m examples.border
"""

import asyncio

from agents import trace

from chapter9.border import call_counterparty
from chapter9.settings import IDENTITY
from examples.common import start
from examples.scripted import TAGS, NordBolt


async def main() -> None:
    _, ledger = start()
    supplier = NordBolt()
    task = {"skill": "quote", "part_number": "BRG-6204", "quantity": 2}
    with trace("parts quote", metadata={**IDENTITY, **TAGS}) as run:
        reply = await call_counterparty(supplier, task, case_id="WO-2R0412")
    print(f"reply: {reply.status}, sent with {supplier.calls[-1]}")
    for key, value in ledger.runs[run.trace_id].borders[0].items():
        shown = "under a second" if key == "latency_ms" else value
        print(f"  {key:<17}{shown}")


if __name__ == "__main__":
    asyncio.run(main())
