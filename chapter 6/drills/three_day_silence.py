"""Failure drill: a task that outlives the process that opened it.

    python -m drills.three_day_silence

A quote task parks while the supplier waits for an answer. Nothing on the
buyer's side stays running. When the answer goes in and the supplier
finishes, the supplier's server posts notifications to the buyer's webhook.
The drill then delivers one notification a second time and sends one with
the wrong token. No API key is needed.
"""

from __future__ import annotations

import asyncio
import json

from chapter6.neighborhood import BUYER_HOST, build_neighborhood
from chapter6.remote import Delegation, answer_supplier_question, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom
from chapter6.webhook import TOKEN_HEADER

WEBHOOK = f"https://{BUYER_HOST}/a2a/notifications/nordbolt"


async def main() -> None:
    hood = build_neighborhood()
    via = Delegation(hood.http, BUYER, CASE)
    inbox = hood.inbox
    delivered: list[dict] = []

    async def record(request) -> None:
        delivered.append(json.loads(request.content))

    hood.outbound.event_hooks["request"].append(record)

    parked = await request_supplier_quote(
        via, "nordbolt", bracket_bom(drawing_rev=None)
    )
    inbox.expect("nordbolt", parked.task_id)
    print(f"task parked     : {parked.error_class}")
    print(f"held, then freed: {len(inbox.work_queue)} notifications")

    await answer_supplier_question(
        via, "nordbolt", parked.task_id, {"drawing_rev": "C"}
    )
    while not any(
        change == "TASK_STATE_COMPLETED" for _, _, change in inbox.work_queue
    ):
        await asyncio.sleep(0.01)
    print("work queue      :")
    for sender, _, change in inbox.work_queue:
        print(f"  {sender}  {change}")

    token = inbox.tokens["nordbolt"]
    last = delivered[-1]
    repeat = await hood.outbound.post(WEBHOOK, json=last, headers={TOKEN_HEADER: token})
    forged = await hood.outbound.post(
        WEBHOOK, json=last, headers={TOKEN_HEADER: "guess"}
    )
    await hood.aclose()
    print(
        f"\nduplicate       : HTTP {repeat.status_code}, queue length {len(inbox.work_queue)}"
    )
    print(
        f"wrong token     : HTTP {forged.status_code}, queue length {len(inbox.work_queue)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
