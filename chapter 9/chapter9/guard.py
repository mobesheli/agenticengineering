"""The tool side of the run budget: tool fees and the repeated-call check."""

from __future__ import annotations

from agents import (
    ToolGuardrailFunctionOutput,
    ToolInputGuardrail,
    ToolInputGuardrailData,
)

from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.pricecard import PriceCard

REPEAT = "That exact call already ran in this task. Use its result."


def budget_guardrail(card: PriceCard) -> ToolInputGuardrail:
    def check(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
        budget: RunBudget = data.context.context.budget
        tool, arguments = data.context.tool_name, data.context.tool_arguments
        if budget.repeated(tool, arguments):
            return ToolGuardrailFunctionOutput.reject_content(
                message=REPEAT, output_info={"reason": "repeated call"}
            )
        fee = card.tool_fee(tool)
        try:
            budget.reserve(fee, "tool")
        except BudgetExceeded as stop:
            return ToolGuardrailFunctionOutput.raise_exception(
                output_info={"reason": stop.reason, "wanted_usd": stop.wanted}
            )
        budget.settle(fee, fee)
        return ToolGuardrailFunctionOutput.allow()

    return ToolInputGuardrail(guardrail_function=check, name="run budget")
