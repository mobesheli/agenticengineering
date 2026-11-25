"""One run of the maintenance planner, span by span, with its cost.

python -m examples.one_run
"""

import asyncio

from chapter9.budget import RunBudget
from chapter9.planner import RunContext, plan_work_order
from examples.common import frontier_agents, routed_agents, show, start
from examples.scripted import MACHINE, TAGS, frontier_run, routed_run


async def main() -> None:
    card, ledger = start()
    budget = RunBudget(1.00)
    agents = frontier_agents(*frontier_run(), card, budget, guarded=False)
    order, trace_id = await plan_work_order(
        MACHINE, agents, RunContext(budget), TAGS
    )
    run = ledger.label(trace_id, "approved", "WO-2R0412", review_minutes=2.0)
    print(f"work order for {order.machine_id}: {order.fault}")
    tags = run.identity
    print(
        f"plant {tags['plant']}, severity {tags['severity']}, for {tags['principal']}"
    )
    print(f"agent {tags['agent_version']}, prompts {tags['prompt_bundle']}")
    print("\nevery step on the frontier model, nothing cached")
    show(run)
    print(f"  outcome {run.outcome} as {run.outcome_ref}, reviewed in 2 minutes")

    budget = RunBudget(1.00)
    agents = routed_agents(*routed_run(), card, budget)
    _, trace_id = await plan_work_order(
        MACHINE, agents, RunContext(budget), TAGS
    )
    print("\nthe same work with a cached prefix and a model for each step")
    show(ledger.runs[trace_id])


if __name__ == "__main__":
    asyncio.run(main())
