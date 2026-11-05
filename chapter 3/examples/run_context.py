"""Values the model must not control travel in the run context.

    python -m examples.run_context

The scripted model calls ``issue_refund`` with the business request only. The
orchestration layer passes ``RunDeps`` as the run context, and the tool reads
the idempotency key and the actor from there. The printout shows the model's
arguments on one side and the context on the other, and that they do not overlap.
"""

from __future__ import annotations

import asyncio
import json

from agents import Agent, Runner, set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message, function_call

from ch3 import payments
from ch3.deps import RunDeps, derive_idempotency_key
from ch3.refund_tools import issue_refund

set_tracing_disabled(True)  # scripted runs never call the API, so there is nothing to export

REFUND_ARGS = {
    "req": {
        "customer_id": "cus_8841",
        "original_charge_id": "ch_3f9a21",
        "amount_cents": 4_500,
        "reason": "Duplicate order shipped",
    }
}


async def main() -> None:
    payments.reset_store()
    payments.set_refund_id_source(["rf_1c2d3e"])
    deps = RunDeps(
        idempotency_key=derive_idempotency_key(
            run_id="run_0007", customer_id="cus_8841", charge_id="ch_3f9a21"
        ),
        actor_id="agent.m.smith@example.com",
    )
    model = ScriptedModel([
        [function_call("issue_refund", REFUND_ARGS, call_id="call_1")],
        [assistant_message("Refund rf_1c2d3e for $45.00 has been issued.")],
    ])
    agent = Agent(
        name="refund-agent",
        instructions="Issue the refund the user asks for.",
        tools=[issue_refund],
        model=model,
    )
    result = await Runner.run(agent, "Refund the duplicate order on charge ch_3f9a21.", context=deps)

    call = next(item for item in result.new_items if item.type == "tool_call_item")
    output = next(item for item in result.new_items if item.type == "tool_call_output_item")
    model_args = json.loads(call.raw_item.arguments)

    print(f"model arguments : {json.dumps(model_args['req'])}")
    print(f"run context     : idempotency_key={deps.idempotency_key} actor_id={deps.actor_id}")
    print(f"tool result     : {output.output}")
    overlap = set(model_args["req"]) & set(RunDeps.model_fields)
    print(f"context fields in the model's arguments: {sorted(overlap) or 'none'}")
    print(f"final output    : {result.final_output}")
    model.assert_complete()


if __name__ == "__main__":
    asyncio.run(main())
