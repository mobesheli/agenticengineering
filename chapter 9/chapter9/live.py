"""Optional live maintenance reader with pre-call model and tool budgets."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from agents import (
    Agent,
    RunConfig,
    RunContextWrapper,
    Runner,
    ToolGuardrailFunctionOutput,
    ToolInputGuardrailData,
    function_tool,
    tool_input_guardrail,
)
from agents.models.interface import Model
from agents.models.openai_provider import OpenAIProvider
from pydantic import BaseModel, Field

from .budget import BudgetExhausted, LoopDetected, Reservation, RunBudget
from .models import MaintenanceCase
from .pricing import load_price_card, normalize_usage, price_model_usage

LIVE_MODEL = "gpt-5-mini"
LIVE_PRICE_KEY = "maintenance-mid"


class DraftWorkOrder(BaseModel):
    case_id: str
    asset_id: str
    probable_fault: str
    parts: list[str] = Field(default_factory=list)
    maintenance_window: str
    confidence: Literal["low", "medium", "high"]


@dataclass
class LiveContext:
    case: MaintenanceCase
    budget: RunBudget
    sensor_summary: dict[str, Any]
    repair_history: list[dict[str, Any]]
    pending_tools: dict[str, Reservation] = field(default_factory=dict)


def _fingerprint(
    context: LiveContext, tool_name: str, arguments: dict[str, Any]
) -> str:
    return context.budget.call_fingerprint(tool_name, arguments)


async def enforce_live_budget(
    data: ToolInputGuardrailData[LiveContext],
) -> ToolGuardrailFunctionOutput:
    try:
        arguments = json.loads(data.context.tool_arguments or "{}")
    except json.JSONDecodeError:
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"reason": "tool arguments were not valid JSON"}
        )
    context = data.context.context
    try:
        reservation = context.budget.reserve_tool(data.context.tool_name, arguments)
    except LoopDetected:
        return ToolGuardrailFunctionOutput.reject_content(
            message="That exact call already ran in this task. Use its result.",
            output_info={"reason": "loop"},
        )
    except BudgetExhausted as exc:
        context.budget.record_stop(context.budget.stop_reason or "budget_exhausted")
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"reason": str(exc), **context.budget.snapshot()}
        )
    except KeyError as exc:
        context.budget.record_stop("unpriced_action")
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"reason": str(exc), **context.budget.snapshot()}
        )
    context.pending_tools[_fingerprint(context, data.context.tool_name, arguments)] = (
        reservation
    )
    return ToolGuardrailFunctionOutput.allow(
        output_info={"price_card_version": context.budget.price_card.version}
    )


live_budget_guardrail = tool_input_guardrail(name="enforce_run_budget")(
    enforce_live_budget
)


def _settle_tool(
    context: LiveContext,
    tool_name: str,
    arguments: dict[str, Any],
) -> None:
    key = _fingerprint(context, tool_name, arguments)
    reservation = context.pending_tools.pop(key)
    context.budget.settle(reservation, context.budget.price_card.tool_cost(tool_name))


class BudgetedOpenAIModel(Model):
    """Reserve a configured ceiling before each non-streamed model request."""

    def __init__(
        self,
        *,
        budget: RunBudget,
        model_name: str = LIVE_MODEL,
        price_key: str = LIVE_PRICE_KEY,
    ) -> None:
        self.budget = budget
        self.model_name = model_name
        self.price_key = price_key
        self.usage_ceiling = {
            "input_tokens": 30_000,
            "cached_input_tokens": 18_000,
            "output_tokens": 4_000,
            "reasoning_tokens": 2_000,
        }
        self._underlying: Model | None = None

    def _model(self) -> Model:
        if self._underlying is None:
            self._underlying = OpenAIProvider().get_model(self.model_name)
        return self._underlying

    async def get_response(self, *args: Any, **kwargs: Any) -> Any:
        reservation = self.budget.reserve_model(self.price_key, self.usage_ceiling)
        try:
            response = await self._model().get_response(*args, **kwargs)
        except Exception:
            self.budget.cancel(reservation)
            raise
        usage = normalize_usage(response.usage)
        actual = price_model_usage(
            usage,
            model=self.price_key,
            card=self.budget.price_card,
        ).total
        self.budget.settle(reservation, actual)
        return response

    async def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise RuntimeError(
            "Chapter 9's budgeted teaching adapter uses non-streamed runs"
        )
        yield  # pragma: no cover

    async def close(self) -> None:
        if self._underlying is not None:
            await self._underlying.close()


def make_live_context(case: MaintenanceCase) -> LiveContext:
    budget = RunBudget(
        price_card=load_price_card(),
        limit_usd=2.0,
        max_calls=12,
        max_steps=12,
        max_seconds=60,
    )
    return LiveContext(
        case=case,
        budget=budget,
        sensor_summary={
            "asset_id": case.asset_id,
            "sensor_code": case.sensor_code,
            "observation": "synthetic anomaly above the reviewed threshold",
        },
        repair_history=[
            {"work_order": "WO-SYNTH-001", "action": "inspection", "result": "stable"}
        ],
    )


def build_maintenance_agent(context: LiveContext) -> Agent[LiveContext]:
    @function_tool(tool_input_guardrails=[live_budget_guardrail])
    def read_sensor_summary(
        ctx: RunContextWrapper[LiveContext], asset_id: str, sensor_code: str
    ) -> dict[str, Any]:
        """Read the synthetic sensor summary for this run's asset."""

        arguments = {"asset_id": asset_id, "sensor_code": sensor_code}
        _settle_tool(ctx.context, "read_sensor_summary", arguments)
        return ctx.context.sensor_summary

    @function_tool(tool_input_guardrails=[live_budget_guardrail])
    def read_repair_history(
        ctx: RunContextWrapper[LiveContext], asset_id: str, limit: int
    ) -> list[dict[str, Any]]:
        """Read a bounded synthetic repair history."""

        arguments = {"asset_id": asset_id, "limit": limit}
        _settle_tool(ctx.context, "read_repair_history", arguments)
        return ctx.context.repair_history[:limit]

    @function_tool(tool_input_guardrails=[live_budget_guardrail])
    def check_parts_catalog(
        ctx: RunContextWrapper[LiveContext], asset_id: str, fault_code: str
    ) -> list[str]:
        """Return synthetic candidate parts for a diagnosed fault."""

        arguments = {"asset_id": asset_id, "fault_code": fault_code}
        _settle_tool(ctx.context, "check_parts_catalog", arguments)
        return [f"PART-{fault_code}-A", f"PART-{fault_code}-B"]

    return Agent(
        name="maintenance_planning_reader",
        model=BudgetedOpenAIModel(budget=context.budget),
        instructions=(
            "Draft one maintenance work order from synthetic sensor and repair data. "
            "Use the smallest useful set of tools. Never repeat an identical tool call. "
            "You may propose; you cannot approve or execute work."
        ),
        tools=[read_sensor_summary, read_repair_history, check_parts_catalog],
        output_type=DraftWorkOrder,
    )


async def run_live_case(case: MaintenanceCase) -> DraftWorkOrder:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the deliberate live route")
    context = make_live_context(case)
    agent = build_maintenance_agent(context)
    result = await Runner.run(
        agent,
        input=(
            f"Draft a proposal for case {case.case_id}, asset {case.asset_id}, "
            f"sensor code {case.sensor_code}."
        ),
        context=context,
        max_turns=8,
        run_config=RunConfig(
            workflow_name="chapter9_maintenance_live",
            trace_include_sensitive_data=False,
            trace_metadata={
                "tenant": "heavy-things-manufacturing",
                "plant": case.plant,
                "principal": f"planner-{case.plant[-1].lower()}-042",
                "agent_version": "9.0.0",
                "prompt_bundle": "maintenance-live-v1",
                "tool_catalog_version": "maintenance-tools-v2",
            },
        ),
    )
    return DraftWorkOrder.model_validate(result.final_output)
