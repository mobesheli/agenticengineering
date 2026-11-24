"""The agent being deployed: a maintenance planner for one manufacturer's plants.

It reads sensor and repair history, looks up a part, and proposes one work order.
A human planner approves the work order before it is created.
"""

from __future__ import annotations

from typing import Any

from agents import Agent, AgentHooks, function_tool
from agents.tool_context import ToolContext

from chapter10.bundle import TEMPLATE, Bundle
from chapter10.contracts import contract_guardrail
from chapter10.models import model_for
from chapter10.platform import Platform, Refused

SENSORS = {
    "P-207": (
        "Coolant pump P-207, plant 2. Bearing vibration in mm/s, last five weekly "
        "readings: 2.9, 3.4, 4.1, 5.2, 6.3. Alarm limit 4.5. Trip limit 7.1."
    ),
    "F-114": (
        "Extraction fan F-114, plant 2. Bearing vibration in mm/s, last five weekly "
        "readings: 1.8, 1.9, 1.8, 2.0, 1.9. Alarm limit 4.5. Trip limit 7.1."
    ),
}
REPAIRS = {
    "P-207": "Bearings last replaced 26 months ago. Recommended interval: 24 months.",
    "F-114": "Bearings replaced 5 months ago. No open work orders.",
}
PARTS = {"BK-6207": {"name": "bearing kit for P-200 series pumps", "lead_days": 3}}


def explain_failure(ctx: Any, error: Exception) -> str:
    """Tell the model why a call failed, so that it reports it and does not retry."""
    if isinstance(error, Refused):
        return f"Refused by the platform: {error}. Do not retry."
    return "The tool failed. Do not retry."


class PlatformHooks(AgentHooks):
    """Asks the gateway before every model call, as a real gateway would be asked."""

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    async def on_llm_start(self, context: Any, agent: Any, *args: Any) -> None:
        self.platform.admit_model_call()


def build_planner(
    platform: Platform, bundle: Bundle, session_id: str, model: Any = None
) -> Agent:
    """The planner for one session, with every tool bound to the platform."""
    parts = contract_guardrail(platform, "parts-catalog")
    orders = contract_guardrail(platform, "work-orders")

    @function_tool(failure_error_function=explain_failure)
    def read_sensor_history(asset_id: str) -> str:
        """Read the recent vibration readings and limits for one asset."""
        platform.check_data("sensor-history")
        return SENSORS.get(asset_id, f"No sensor history for {asset_id}.")

    @function_tool(failure_error_function=explain_failure)
    def get_repair_history(asset_id: str) -> str:
        """Read the repair history for one asset."""
        platform.check_data("repair-history")
        return REPAIRS.get(asset_id, f"No repair history for {asset_id}.")

    @function_tool(
        tool_input_guardrails=[parts], failure_error_function=explain_failure
    )
    def search_parts(query: str) -> str:
        """Search the parts catalog. Returns part numbers and names."""
        platform.check_identity("parts-catalog")
        words = query.lower().split()
        found = [n for n, p in PARTS.items() if any(w in p["name"] for w in words)]
        return ", ".join(f"{n}: {PARTS[n]['name']}" for n in found) or "No match."

    @function_tool(
        tool_input_guardrails=[parts], failure_error_function=explain_failure
    )
    def get_lead_time(part_number: str) -> str:
        """Lead time in days for one part number."""
        platform.check_identity("parts-catalog")
        part = PARTS.get(part_number)
        return f"{part['lead_days']} days" if part else f"Unknown part {part_number}."

    @function_tool(
        tool_input_guardrails=[parts], failure_error_function=explain_failure
    )
    def create_order(part_number: str, quantity: int) -> str:
        """Place a purchase order for a part."""
        platform.check_identity("parts-catalog", needs="write")
        return f"Purchase order placed for {quantity} x {part_number}."

    @function_tool(
        needs_approval=True,
        tool_input_guardrails=[orders],
        failure_error_function=explain_failure,
    )
    def create_work_order(
        ctx: ToolContext, asset_id: str, action: str, part_number: str
    ) -> str:
        """Create one work order. A human planner approves it first."""
        platform.check_identity("work-orders", needs="write")
        if asset_id not in SENSORS:
            return f"No work order created: {asset_id} is not a known asset."
        key = f"{session_id}:{ctx.tool_call_id}"
        if key not in platform.work_orders:
            number = f"WO-{4100 + len(platform.work_orders)}"
            platform.work_orders[key] = {
                "number": number,
                "asset": asset_id,
                "action": action,
                "part": part_number,
                "bundle": bundle.bundle,
            }
        return f"{platform.work_orders[key]['number']} created for {asset_id}."

    prompt_file = bundle.prompts.partition("@")[0]
    pinned_model, settings = model_for(bundle)
    return Agent(
        name="maintenance_planner",
        instructions=(TEMPLATE / prompt_file).read_text(),
        tools=[
            read_sensor_history,
            get_repair_history,
            search_parts,
            get_lead_time,
            create_order,
            create_work_order,
        ],
        model=model or pinned_model,
        model_settings=settings,
        hooks=PlatformHooks(platform),
    )
