"""The worker, the approval queue, and the tool contracts, through the real SDK runner."""

from __future__ import annotations

import asyncio

import pytest
from agents import Runner, set_tracing_disabled
from agents.testing import function_call

from chapter10.bundle import load_bundle
from chapter10.platform import Refused
from chapter10.worker import ParkedRuns, resume, run_turn, session_for
from examples.scripted import (
    HEALTHY,
    OVERREACH,
    PLAN,
    closing,
    scripted_planner,
    staging,
)

set_tracing_disabled(True)
REQUEST = "Pump P-207 vibrates more every week. Plan the maintenance."
RELEASE = "maintenance-planner@41.3"


@pytest.fixture
async def store(tmp_path):
    runs = await ParkedRuns.open(f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}")
    yield runs
    await runs.engine.dispose()


def planner(platform, turns, session="s1"):
    return scripted_planner(platform, load_bundle(), session, turns)


async def test_a_healthy_asset_finishes_without_an_approval(store):
    platform = staging()
    result = await run_turn(
        planner(platform, HEALTHY), store, "s1", "Check F-114.", RELEASE
    )
    assert result["status"] == "done"
    assert platform.work_orders == {}


async def test_a_work_order_waits_and_nothing_is_created_before_the_decision(store):
    platform = staging()
    result = await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)
    assert result["status"] == "waiting"
    assert result["asks"][0].startswith("create_work_order")
    assert platform.work_orders == {}
    assert await store.statuses() == {result["run_id"]: "waiting"}


async def test_another_worker_resumes_and_keeps_the_session_history(store):
    platform = staging()
    first = await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)
    agent = planner(platform, closing("The work order is created."))
    done = await resume(agent, store, first["run_id"], True, RELEASE)
    assert done["status"] == "done"
    assert [order["number"] for order in platform.work_orders.values()] == ["WO-4100"]
    history = await session_for(store, "s1").get_items()
    assert len(history) >= 11
    assert await store.statuses() == {first["run_id"]: "approved"}


async def test_a_rejected_work_order_is_never_created(store):
    platform = staging()
    first = await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)
    agent = planner(platform, closing("The planner declined the work order."))
    done = await resume(agent, store, first["run_id"], False, RELEASE)
    assert done["status"] == "done"
    assert platform.work_orders == {}
    assert await store.statuses() == {first["run_id"]: "rejected"}


async def test_one_approval_cannot_be_used_twice(store):
    platform = staging()
    first = await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)
    agent = planner(platform, closing("The work order is created."))
    await resume(agent, store, first["run_id"], True, RELEASE)
    again = await resume(agent, store, first["run_id"], True, RELEASE)
    assert again["status"] == "gone"
    assert len(platform.work_orders) == 1


async def test_an_unknown_run_is_gone(store):
    agent = planner(staging(), closing("x"))
    assert (await resume(agent, store, "no-such-run", True, RELEASE))[
        "status"
    ] == "gone"


async def test_a_run_parked_under_an_old_release_is_void(store):
    platform = staging()
    first = await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)
    agent = planner(platform, closing("x"))
    stale = await resume(
        agent, store, first["run_id"], True, "maintenance-planner@41.4"
    )
    assert stale["status"] == "stale"
    assert platform.work_orders == {}
    assert await store.statuses() == {first["run_id"]: "stale"}


async def test_the_contract_refuses_an_operation_before_it_runs():
    platform = staging()
    result = await Runner.run(planner(platform, OVERREACH), "Order two bearing kits.")
    kinds = [kind for kind, _ in platform.audit]
    assert kinds == ["contract", "policy_denied"]
    assert "not permitted" in result.final_output


async def test_revoking_one_operation_takes_effect_without_a_redeploy(store):
    platform = staging()
    contract = platform.contracts["work-orders"]
    first = await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)
    platform.contracts["work-orders"] = contract.model_copy(update={"allow": []})
    agent = planner(platform, closing("I could not create the work order."))
    await resume(agent, store, first["run_id"], True, RELEASE)
    assert platform.work_orders == {}
    assert (
        "policy_denied",
        "work-orders.create_work_order: outside contract 1.4.0",
    ) in (platform.audit)


async def test_the_server_refuses_what_a_loose_contract_lets_through():
    platform = staging()
    contract = platform.contracts["parts-catalog"]
    loose = contract.model_copy(
        update={"allow": [*contract.allow, "create_order"], "never": []}
    )
    platform.contracts["parts-catalog"] = loose
    await Runner.run(planner(platform, OVERREACH), "Order two bearing kits.")
    assert platform.audit[-1][0] == "server_refused"


async def test_a_tool_with_no_contract_is_refused():
    platform = staging()
    del platform.contracts["parts-catalog"]
    await Runner.run(planner(platform, OVERREACH), "Order two bearing kits.")
    assert platform.audit[0] == ("policy_denied", "parts-catalog: no contract, refused")


async def test_a_zero_budget_at_the_gateway_stops_the_model_call(store):
    platform = staging()
    platform.budget_usd = 0.0
    with pytest.raises(Refused, match="gateway"):
        await run_turn(planner(platform, PLAN), store, "s1", REQUEST, RELEASE)


async def test_an_uncertified_data_product_is_not_read():
    platform = staging()
    platform.certified["sensor-history"] = False
    await Runner.run(planner(platform, HEALTHY), "Check F-114.")
    assert ("data_refused", "sensor-history") in platform.audit


async def test_many_workers_share_one_store_without_losing_a_run(store):
    async def one(index: int) -> tuple[str, int]:
        platform, session = staging(), f"s{index}"
        first = await run_turn(
            planner(platform, PLAN, session), store, session, REQUEST, RELEASE
        )
        agent = planner(platform, closing("The work order is created."), session)
        done = await resume(agent, store, first["run_id"], True, RELEASE)
        return done["status"], len(platform.work_orders)

    results = await asyncio.gather(*[one(index) for index in range(24)])
    assert results == [("done", 1)] * 24
    assert set((await store.statuses()).values()) == {"approved"}


async def test_a_work_order_for_an_unknown_asset_is_not_created(store):
    platform = staging()
    order = {"asset_id": "C-999", "action": "Inspect", "part_number": ""}
    turns = [[function_call("create_work_order", order, call_id="call_1")]]
    first = await run_turn(
        planner(platform, turns), store, "s1", "Plan C-999.", RELEASE
    )
    agent = planner(platform, closing("No work order was created."))
    await resume(agent, store, first["run_id"], True, RELEASE)
    assert platform.work_orders == {}


async def test_a_refusal_reaches_the_model_with_its_reason_and_no_invitation_to_retry():
    platform = staging()
    platform.certified["sensor-history"] = False
    result = await Runner.run(planner(platform, HEALTHY), "Check F-114.")
    outputs = [
        item.output for item in result.new_items if item.type == "tool_call_output_item"
    ]
    assert outputs[0] == (
        "Refused by the platform: data product sensor-history is not certified. Do not retry."
    )
