"""Failure drill two: the reviewer says no.

    python -m drills.reject_approval

The scripted model calls ``execute_refund`` for $214.50, which is above the
approval threshold, so the run stops and returns one interruption. A scripted
reviewer rejects it with a reason. The orchestration layer records the
rejection on the run state and runs the agent again from that state. The tool
never executes; the model is told why and tells the user. No API key is needed.
"""

from __future__ import annotations

import asyncio
import json
import textwrap

from agents import Agent, set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message, function_call

from ch3 import payments
from ch3.approvals import ScriptedReviewer, pending_arguments, run_with_approvals
from ch3.deps import RunDeps, derive_idempotency_key
from ch3.refund_tools import execute_refund

set_tracing_disabled(True)  # scripted runs never call the API, so there is nothing to export

REFUND_ARGS = {
    "customer_id": "cus_8841",
    "original_charge_id": "ch_3f9a21",
    "amount_cents": 21_450,
    "reason": "Damaged on arrival",
}

REJECTION_REASON = "Amount exceeds the self-service limit for this customer tier"

FINAL_MESSAGE = (
    "I was not able to issue the $214.50 refund. A reviewer declined it because the "
    "amount exceeds the self-service limit for this customer tier. I can raise it "
    "with the billing team if you would like."
)


async def main() -> None:
    payments.reset_store()
    deps = RunDeps(
        idempotency_key=derive_idempotency_key(
            run_id="run_0043", customer_id="cus_8841", charge_id="ch_3f9a21"
        ),
        actor_id="agent.m.smith@example.com",
    )
    model = ScriptedModel([
        [function_call("execute_refund", REFUND_ARGS, call_id="call_refund")],
        [assistant_message(FINAL_MESSAGE)],
    ])
    refund_agent = Agent(
        name="refund-agent",
        instructions="Execute the previewed refund. If it is refused, explain why.",
        tools=[execute_refund],
        model=model,
    )
    reviewer = ScriptedReviewer(approve=False, reason=REJECTION_REASON)

    result = await run_with_approvals(
        refund_agent, "Refund charge ch_3f9a21, it arrived damaged.", deps, reviewer
    )

    (item,) = reviewer.seen
    args = pending_arguments(item)
    print(f"interruption : {item.name}")
    for key, value in args.items():
        print(f"               {key}={json.dumps(value)}")
    print(f"reviewer     : rejected")
    print(f"reason       : {REJECTION_REASON}")
    ran = payments.count_refunds() > 0
    print(f"tool ran     : {'yes' if ran else 'no'} (refunds in store: {payments.count_refunds()})")
    lines = textwrap.wrap(str(result.final_output), width=58)
    print(f"final output : {lines[0]}")
    for line in lines[1:]:
        print(f"               {line}")
    model.assert_complete()


if __name__ == "__main__":
    asyncio.run(main())
