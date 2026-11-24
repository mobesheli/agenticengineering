"""Write decisions, sign a checkpoint, then tamper with the log three ways.

python -m examples.audit_demo
"""

from __future__ import annotations

import asyncio

from agents import set_tracing_disabled

from chapter8.audit import Checkpoint
from examples.reconcile import run as reconcile


async def run() -> None:
    harness = await reconcile(live=False, show=False)
    records = harness.log.records()
    mark = harness.notary.checkpoint(harness.log)
    print(
        f"checkpoint          {mark.count} records, head {mark.head[:12]}, signed"
    )
    print(f"untouched log       {harness.notary.verify(records, mark)}")

    edited = [record.model_copy() for record in records]
    edited[0] = edited[0].model_copy(
        update={"approver": "Practitioner/dr-nobody"}
    )
    print(f"approver edited     {harness.notary.verify(edited, mark)}")

    print(f"last record dropped {harness.notary.verify(records[:-1], mark)}")

    rewritten = []
    previous = "0" * 64
    for record in edited:
        relinked = record.model_copy(update={"prev_hash": previous})
        rewritten.append(relinked)
        previous = relinked.digest()
    print(f"chain recomputed    {harness.notary.verify(rewritten, mark)}")
    forged = Checkpoint(mark.count, previous, mark.signature)
    print(f"checkpoint forged   {harness.notary.verify(rewritten, forged)}")


def main() -> None:
    set_tracing_disabled(True)
    asyncio.run(run())


if __name__ == "__main__":
    main()
