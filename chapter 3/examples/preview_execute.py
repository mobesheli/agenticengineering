"""Preview, then execute against the previewed content hash.

    python -m examples.preview_execute

Run one: the scripted model previews a refund, then executes it carrying the
hash from the preview, and the refund is issued. Run two: the model presents a
stale hash and the execute tool refuses with a structured error instead of
writing anything.
"""

from __future__ import annotations

import asyncio

from agents import Agent, Runner, set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message, function_call

from ch3 import payments
from ch3.deps import RunDeps, derive_idempotency_key
from ch3.previews import content_hash, execute_previewed_refund, preview_refund
from ch3.refund_tools import RefundRequest

set_tracing_disabled(True)  # scripted runs never call the API, so there is nothing to export

REQUEST = RefundRequest(
    customer_id="cus_8841",
    original_charge_id="ch_3f9a21",
    amount_cents=4_500,
    reason="Duplicate order shipped",
)


def tool_outputs(result) -> list:
    return [item.output for item in result.new_items if item.type == "tool_call_output_item"]


async def main() -> None:
    payments.reset_store()
    payments.set_refund_id_source(["rf_1c2d3e"])
    deps = RunDeps(
        idempotency_key=derive_idempotency_key(
            run_id="run_0008", customer_id=REQUEST.customer_id,
            charge_id=REQUEST.original_charge_id,
        ),
        actor_id="agent.m.smith@example.com",
    )
    req = REQUEST.model_dump()
    good_hash = content_hash(REQUEST)

    matching = ScriptedModel([
        [function_call("preview_refund", {"req": req}, call_id="call_1")],
        [function_call("execute_previewed_refund",
                       {**req, "content_hash": good_hash}, call_id="call_2")],
        [assistant_message("The refund was issued as previewed.")],
    ])
    agent = Agent(
        name="refund-agent",
        instructions="Preview every refund, then execute it with the previewed hash.",
        tools=[preview_refund, execute_previewed_refund],
        model=matching,
    )
    result = await Runner.run(agent, "Refund the duplicate order.", context=deps)
    preview, executed = tool_outputs(result)
    print(f"preview        : amount_cents={preview.amount_cents} content_hash={preview.content_hash}")
    print(f"execute (match): status={executed.status} refund_id={executed.refund_id}")
    matching.assert_complete()

    stale = ScriptedModel([
        [function_call("execute_previewed_refund",
                       {**req, "content_hash": "0000000000000000"}, call_id="call_3")],
        [assistant_message("The details changed since the preview, so I did not execute.")],
    ])
    agent.model = stale
    result = await Runner.run(agent, "Refund the duplicate order.", context=deps)
    (refused,) = tool_outputs(result)
    print(f"execute (stale): refused error_class={refused['error_class']} "
          f"retryable={refused['retryable']} hint={refused['machine_action_hint']}")
    print(f"refunds in store: {payments.count_refunds()}")
    stale.assert_complete()


if __name__ == "__main__":
    asyncio.run(main())
