"""A tool contract refuses an operation before the call, and the server refuses it again.

python -m examples.contract_demo
"""

from __future__ import annotations

import asyncio

from agents import Runner, set_tracing_disabled

from chapter10.bundle import load_bundle
from examples.scripted import OVERREACH, scripted_planner, staging


async def main() -> list[str]:
    set_tracing_disabled(True)
    bundle, platform = load_bundle(), staging()
    contract = platform.contracts["parts-catalog"]
    lines = [
        f"contract {contract.tool}@{contract.version}",
        f"  allow  {', '.join(contract.allow)}",
        f"  never  {', '.join(contract.never)}",
    ]
    agent = scripted_planner(platform, bundle, "demo", OVERREACH)
    result = await Runner.run(agent, "Order two bearing kits for pump P-207.")
    lines.append("the agent searches the catalog, then tries to place an order")
    lines += [f"  {kind:15}{detail}" for kind, detail in platform.audit]
    lines.append(f"  the agent's reply: {result.final_output}")

    loose = contract.model_copy(
        update={"allow": [*contract.allow, "create_order"], "never": []}
    )
    platform.contracts["parts-catalog"] = loose
    platform.audit.clear()
    await Runner.run(
        scripted_planner(platform, bundle, "demo", OVERREACH), "Order them."
    )
    lines.append("the same request after someone loosens the contract by mistake")
    lines += [f"  {kind:15}{detail}" for kind, detail in platform.audit]
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    asyncio.run(main())
