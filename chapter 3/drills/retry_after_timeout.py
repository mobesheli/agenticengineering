"""Failure drill one: the response is lost and the orchestration layer retries.

    python -m drills.retry_after_timeout

The orchestration layer derives an idempotency key, runs the agent, and the
agent calls ``issue_refund``. The refund is written. Then the response to the
caller is lost, the way a gateway loses one, and the orchestration layer does
what any at-least-once system does: it retries with the same key. The second
call replays the first refund instead of issuing another. No API key is needed;
the model is the SDK's scripted test double.
"""

from __future__ import annotations

import asyncio

from agents import Agent, RunResult, Runner, set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message, function_call

from ch3 import payments
from ch3.deps import RunDeps, derive_idempotency_key
from ch3.refund_tools import RefundResult, issue_refund

REFUND_ARGS = {
    "req": {
        "customer_id": "cus_8841",
        "original_charge_id": "ch_3f9a21",
        "amount_cents": 21_450,
        "reason": "Damaged on arrival",
    }
}

set_tracing_disabled(True)  # scripted runs never call the API, so there is nothing to export


class ResponseLost(Exception):
    """The downstream action completed but the response never arrived."""


class LossyChannel:
    """Delivers run results to the caller, dropping the first one on the floor."""

    def __init__(self, drop_first: bool = True) -> None:
        self._drop_next = drop_first

    def deliver(self, result: RunResult) -> RunResult:
        if self._drop_next:
            self._drop_next = False
            raise ResponseLost("gateway timeout after the processor accepted the request")
        return result


def scripted_model() -> ScriptedModel:
    """One tool call, then a short confirmation."""
    return ScriptedModel([
        [function_call("issue_refund", REFUND_ARGS, call_id="call_refund")],
        [assistant_message("The refund has been issued.")],
    ])


def refund_result(result: RunResult) -> RefundResult:
    """Pull the typed tool result out of the run, the way a trace would."""
    for item in result.new_items:
        if item.type == "tool_call_output_item" and isinstance(item.output, RefundResult):
            return item.output
    raise LookupError("issue_refund did not run")


async def main() -> None:
    payments.reset_store()
    payments.set_refund_id_source(["rf_7f3a9c", "rf_000bad"])
    deps = RunDeps(
        idempotency_key=derive_idempotency_key(
            run_id="run_0042", customer_id="cus_8841", charge_id="ch_3f9a21"
        ),
        actor_id="agent.m.smith@example.com",
    )
    channel = LossyChannel()

    async def attempt() -> RunResult:
        agent = Agent(
            name="refund-agent",
            instructions="Issue the refund the user asks for.",
            tools=[issue_refund],
            model=scripted_model(),
        )
        result = await Runner.run(agent, "Refund charge ch_3f9a21, it arrived damaged.", context=deps)
        return channel.deliver(result)

    try:
        await attempt()
    except ResponseLost:
        first = payments.db.execute(
            "SELECT refund_id, amount_cents FROM refunds WHERE idempotency_key = ?",
            (deps.idempotency_key,),
        ).fetchone()
        print(f"first call : issued   refund_id={first[0]} amount_cents={first[1]}")
        print("network    : response lost, orchestration retries with the same key")
        second = refund_result(await attempt())
        print(f"second call: {second.status} refund_id={second.refund_id} "
              f"amount_cents={second.amount_cents}")
    print(f"refunds in store: {payments.count_refunds()}")


if __name__ == "__main__":
    asyncio.run(main())
