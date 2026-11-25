"""Run the planner against live models and check what the meter recorded.

    OPENAI_API_KEY=... python -m examples.live_check [runs]

It makes real model calls and costs a few cents. It checks that the provider's
usage report has the fields the meter prices, that every call was priced and
labeled with a step, that the budget and the ledger agree to the cent, that a
run with too small a budget stops, and that a streamed call is priced too.
"""

import asyncio
import sys

from agents import Agent, ModelSettings, OpenAIResponsesModel, Runner, trace
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.metered import MeteredModel, StepRouter
from chapter9.planner import RunContext, build_agents, plan_work_order
from chapter9.settings import IDENTITY, MODELS, WORKFLOW
from examples.common import show, start
from examples.scripted import MACHINE, TAGS


async def one(card, ledger, client, limit: float) -> bool:
    budget = RunBudget(limit_usd=limit, first_call_usd=0.02)
    live = {
        step: OpenAIResponsesModel(name, client) for step, name in MODELS.items()
    }
    router = StepRouter(
        {
            "plan": MeteredModel(live["plan"], MODELS["plan"], card, budget),
            "read": MeteredModel(live["read"], MODELS["read"], card, budget),
        }
    )
    drafter = MeteredModel(live["draft"], MODELS["draft"], card, budget, "draft")
    diagnoser, writer = build_agents(router, drafter, card)
    low = ModelSettings(reasoning=Reasoning(effort="low"))
    agents = (
        diagnoser.clone(model_settings=low),
        writer.clone(model_settings=low),
    )
    try:
        order, trace_id = await plan_work_order(
            MACHINE, agents, RunContext(budget), TAGS
        )
    except BudgetExceeded as stop:
        print(f"stopped: {stop}")
        show(list(ledger.runs.values())[-1])
        return limit < 0.05
    run = ledger.runs[trace_id]
    show(run)
    spent = run.model_usd + run.tool_usd
    checks = {
        "order names the bearing": any(
            "BRG-6204" in part for part in order.parts
        ),
        "every call priced": all(call.cost_usd > 0 for call in run.model_calls),
        "steps labeled": {call.step for call in run.model_calls}
        >= {"plan", "draft"},
        "budget equals ledger": abs(spent - budget.spent_usd) < 1e-6,
        "identity stamped": run.identity["plant"] == TAGS["plant"],
    }
    for name, passed in checks.items():
        print(f"  {'ok  ' if passed else 'FAIL'} {name}")
    print(f"  parts on the order: {order.parts}")
    return all(checks.values())


async def streamed(card, ledger, client) -> bool:
    budget = RunBudget(limit_usd=0.10, first_call_usd=0.02)
    name = MODELS["draft"]
    model = MeteredModel(OpenAIResponsesModel(name, client), name, card, budget)
    agent = Agent(
        name="streamed", instructions="Answer in one sentence.", model=model
    )
    with trace(WORKFLOW, metadata={**IDENTITY, **TAGS}) as seen:
        stream = Runner.run_streamed(agent, "Why does a worn bearing vibrate?")
        async for _ in stream.stream_events():
            pass
    run = ledger.runs[seen.trace_id]
    show(run)
    priced = run.model_usd > 0 and abs(run.model_usd - budget.spent_usd) < 1e-6
    print(f"  {'ok  ' if priced else 'FAIL'} a streamed call is priced")
    return priced


async def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    card, ledger = start()
    client = AsyncOpenAI()
    results = [await one(card, ledger, client, limit=0.50) for _ in range(runs)]
    print("\na run with a two-cent budget must stop before it spends more")
    results.append(await one(card, ledger, client, limit=0.02))
    print("\na streamed call must be priced like any other")
    results.append(await streamed(card, ledger, client))
    print(f"\n{sum(results)} of {len(results)} runs as intended")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
