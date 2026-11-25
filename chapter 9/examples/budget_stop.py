"""A model that repeats itself, a guard that refuses, and a budget that stops it.

python -m examples.budget_stop
"""

import asyncio

from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.metered import MeteredModel
from chapter9.planner import RunContext, plan_work_order
from chapter9.pricecard import UnknownPrice
from examples.common import frontier_agents, show, start
from examples.scripted import MACHINE, TAGS, frontier_run, stuck_run


async def main() -> None:
    card, ledger = start()
    budget = RunBudget(limit_usd=0.20, model_calls=8, tool_calls=8)
    agents = frontier_agents(*stuck_run(), card, budget, guarded=True)
    print(f"run budget ${budget.limit_usd:.2f}, 8 model calls, 8 tool calls")
    try:
        await plan_work_order(MACHINE, agents, RunContext(budget), TAGS)
    except BudgetExceeded as stop:
        trace_id = list(ledger.runs)[-1]
        run = ledger.label(trace_id, "stopped", "none", review_minutes=0.0)
        show(run)
        print(f"stopped: {stop}")
        print(f"  outcome {run.outcome}, model calls left {budget.model_calls}")

    parent = RunBudget(limit_usd=0.10)
    child = parent.child(limit_usd=0.50)
    print("\na child asks for $0.50 from a parent that has $0.10 left")
    print(f"the child is given ${child.limit_usd:.2f}")
    child.reserve(0.06, "model")
    child.settle(0.06, 0.06)
    print(f"the child spends $0.06: parent has ${parent.remaining_usd:.2f} left")

    unpriced = MeteredModel(
        frontier_run()[0], "gpt-7-preview", card, RunBudget(1.00)
    )
    try:
        await unpriced.get_response(None, "hello")
    except UnknownPrice as error:
        print(f"\nnot on the card: {error}")


if __name__ == "__main__":
    asyncio.run(main())
