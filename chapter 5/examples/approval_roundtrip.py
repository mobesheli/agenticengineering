"""Pause a run for approval, store it, and resume it from the database.

python -m examples.approval_roundtrip              # needs OPENAI_API_KEY
python -m examples.approval_roundtrip --scripted   # no key: scripted model replies
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from chapter5 import approvals
from chapter5.approvals import (
    ApprovalStore,
    PaymentCase,
    advance_payment,
    resume_payment,
)

CASE = PaymentCase(
    case_id="case-118",
    request="Release payment pay-118 for 7,500.00 EUR, which is 750000 cents.",
    evidence=[
        "Invoice inv-552 matches the purchase order.",
        "Beneficiary verified in March.",
    ],
)


async def main(scripted_run: bool = False) -> None:
    if scripted_run:
        from examples.scripted import calls, says, scripted

        approvals.payments_agent = scripted(
            approvals.payments_agent,
            calls(
                "release_payment", {"payment_id": "pay-118", "amount_cents": 750_000}
            ),
            says("Payment pay-118 was approved and released."),
        )
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / "pending.db")
        status = await advance_payment(CASE, ApprovalStore(path))
        print(f"worker A : {status.state}, released so far: {approvals.RELEASED}")
        done = await resume_payment(CASE.case_id, True, "", ApprovalStore(path))
        print(f"worker B : {done.state}, released: {approvals.RELEASED}")
        print(f"worker B : {done.outcome}")


if __name__ == "__main__":
    asyncio.run(main(scripted_run="--scripted" in sys.argv))
