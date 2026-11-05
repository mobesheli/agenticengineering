"""Persist a paused run, rebuild it elsewhere, approve, and resume.

    python -m examples.resume_from_string

The process that asks for approval and the process that resumes the run can be
different machines on different days. Here they are two functions that share
nothing but a file. The first runs the agent until it pauses on
``execute_refund``, serializes the state with ``state.to_string()``, and writes
it to disk. The second reads the blob, rebuilds the state with
``RunState.from_string`` and a ``context_override`` so the run context comes
back as a ``RunDeps`` rather than a dictionary, approves the pending call, and
resumes. The tool then reads ``ctx.context.idempotency_key`` and the refund is
issued under the key the first process derived.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from agents import Agent, Runner, set_tracing_disabled
from agents.run_state import RunState
from agents.testing import ScriptedModel, assistant_message, function_call

from ch3 import payments
from ch3.deps import RunDeps, derive_idempotency_key
from ch3.refund_tools import RefundResult, execute_refund

set_tracing_disabled(True)  # scripted runs never call the API, so there is nothing to export

REFUND_ARGS = {
    "customer_id": "cus_8841",
    "original_charge_id": "ch_3f9a21",
    "amount_cents": 21_450,
    "reason": "Damaged on arrival",
}


def build_agent(model: ScriptedModel) -> Agent[RunDeps]:
    """Both processes build the same agent from the same code."""
    return Agent(
        name="refund-agent",
        instructions="Execute the previewed refund. If it is refused, explain why.",
        tools=[execute_refund],
        model=model,
    )


def build_deps() -> RunDeps:
    """Both processes derive the same key from the same intent."""
    return RunDeps(
        idempotency_key=derive_idempotency_key(
            run_id="run_0044", customer_id="cus_8841", charge_id="ch_3f9a21"
        ),
        actor_id="agent.m.smith@example.com",
    )


async def process_that_asks(state_file: Path) -> None:
    """Run until the approval gate, then persist the state and stop."""
    model = ScriptedModel([
        [function_call("execute_refund", REFUND_ARGS, call_id="call_refund")],
    ])
    refund_agent = build_agent(model)
    deps = build_deps()
    result = await Runner.run(refund_agent, "Refund charge ch_3f9a21.", context=deps)
    (item,) = result.interruptions
    state = result.to_state()
    blob = state.to_string()
    state_file.write_text(blob)
    print(f"process A : paused on {item.name}, state persisted ({len(blob)} bytes)")
    print(f"process A : key in context {deps.idempotency_key}")


async def process_that_resumes(state_file: Path) -> RefundResult:
    """Read the state back, restore the context type, approve, and resume."""
    model = ScriptedModel([
        [assistant_message("The refund was approved and issued.")],
    ])
    refund_agent = build_agent(model)
    deps = build_deps()
    blob = state_file.read_text()
    state = await RunState.from_string(refund_agent, blob, context_override=deps)
    for item in state.get_interruptions():
        state.approve(item)
    result = await Runner.run(refund_agent, state)
    output = next(
        item.output for item in result.new_items if item.type == "tool_call_output_item"
    )
    print("process B : rebuilt state with context_override, approved, resumed")
    print(f"process B : tool result {output}")
    print(f"process B : final output {result.final_output}")
    model.assert_complete()
    return output


async def main() -> None:
    payments.reset_store()
    payments.set_refund_id_source(["rf_7f3a9c"])
    with tempfile.TemporaryDirectory() as folder:
        state_file = Path(folder) / "run_0044.state.json"
        await process_that_asks(state_file)
        await process_that_resumes(state_file)
    stored = payments.db.execute(
        "SELECT idempotency_key FROM refunds WHERE refund_id = ?", ("rf_7f3a9c",)
    ).fetchone()
    print(f"store     : refund rf_7f3a9c written under key {stored[0]}")
    print(f"key match : {'yes' if stored[0] == build_deps().idempotency_key else 'no'}")


if __name__ == "__main__":
    asyncio.run(main())
