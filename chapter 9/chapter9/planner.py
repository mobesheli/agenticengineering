"""The maintenance planner: a diagnosis step and a drafting step, run by code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import yaml
from agents import Agent, Model, Runner, function_tool, trace
from agents.exceptions import ToolInputGuardrailTripwireTriggered
from pydantic import BaseModel

from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.guard import budget_guardrail
from chapter9.pricecard import PriceCard
from chapter9.settings import DATA, IDENTITY, WORKFLOW

PLANT = yaml.safe_load((DATA / "plant.yaml").read_text())


@dataclass
class RunContext:
    budget: RunBudget


class Diagnosis(BaseModel):
    machine_id: str
    fault: str
    parts: list[str]
    confidence: Literal["low", "medium", "high"]


class WorkOrder(BaseModel):
    machine_id: str
    fault: str
    parts: list[str]
    window: str
    steps: list[str]


def plant_tools(card: PriceCard, guarded: bool) -> list:
    limits = [budget_guardrail(card)] if guarded else []

    @function_tool(tool_input_guardrails=limits)
    def read_sensor_summary(machine_id: str) -> str:
        """Read the latest sensor summary the plant published for a machine."""
        return PLANT["machines"][machine_id]["sensor_summary"]

    @function_tool(tool_input_guardrails=limits)
    def read_repair_history(machine_id: str) -> str:
        """Read the repair history of a machine, newest entry last."""
        return "\n".join(PLANT["machines"][machine_id]["history"])

    @function_tool(tool_input_guardrails=limits)
    def search_manual(query: str) -> str:
        """Search the maintenance manuals."""
        asked = query.lower()
        hits = [
            text
            for title, text in PLANT["manual"].items()
            if all(word in asked for word in title.split())
        ]
        return "\n".join(hits) or "no manual section matched"

    @function_tool(tool_input_guardrails=limits)
    def check_parts(part_number: str) -> str:
        """Check stock and lead time for a part in the parts catalog."""
        part = PLANT["parts"].get(part_number.strip().upper())
        if part is None:
            return f"{part_number} is not in the parts catalog"
        return f"{part['description']}: {part['stock']} in stock"

    return [read_sensor_summary, read_repair_history, search_manual, check_parts]


def build_agents(
    diagnose: Model, draft: Model, card: PriceCard, guarded: bool = True
) -> tuple[Agent, Agent]:
    diagnoser = Agent(
        name="diagnoser",
        instructions=(
            "You diagnose machine faults for a maintenance planner. Read the "
            "sensor summary and the repair history, check the manual and the "
            "parts catalog when they help, and return a diagnosis. Call each "
            "tool once for each question. You never act on a machine."
        ),
        model=diagnose,
        tools=plant_tools(card, guarded),
        output_type=Diagnosis,
    )
    drafter = Agent(
        name="drafter",
        instructions=(
            "Turn the diagnosis you are given into a work order for a human "
            "planner to approve. Use only what the diagnosis says."
        ),
        model=draft,
        output_type=WorkOrder,
    )
    return diagnoser, drafter


async def plan_work_order(
    machine_id: str,
    agents: tuple[Agent, Agent],
    context: RunContext,
    tags: dict[str, str],
) -> tuple[WorkOrder, str]:
    """One run: diagnose, then draft. Returns the order and the trace id.

    A budget stop reaches the caller as BudgetExceeded whether the meter raised
    it before a model call or the tool guardrail tripped before a tool call.
    """
    diagnoser, drafter = agents
    ask = f"Machine {machine_id} raised a vibration alert. Diagnose it."
    try:
        with trace(WORKFLOW, metadata={**IDENTITY, **tags}) as run:
            found = await Runner.run(
                diagnoser, ask, context=context, max_turns=10
            )
            brief = found.final_output.model_dump_json()
            order = await Runner.run(
                drafter, brief, context=context, max_turns=3
            )
    except ToolInputGuardrailTripwireTriggered as tripped:
        why = tripped.output.output_info
        raise BudgetExceeded(
            why["reason"], context.budget, why["wanted_usd"]
        ) from tripped
    return order.final_output, run.trace_id
