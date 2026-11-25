"""The ledger: one record for each run, joining identity, cost, and outcome."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.tracing.processor_interface import TracingProcessor

from chapter9.guard import REPEAT
from chapter9.pricecard import PriceCard

IDENTITY_KEYS = (
    "tenant",
    "plant",
    "severity",
    "principal",
    "agent_version",
    "prompt_bundle",
    "tool_catalog",
)
TRIPPED = "triggered tripwire"
SUCCESS = "approved"
OUTCOMES = (SUCCESS, "edited", "rejected", "stopped")


@dataclass(frozen=True)
class ModelCall:
    step: str
    model: str
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: str
    fee_usd: float
    failed: bool = False
    repeat: bool = False
    refused: bool = False
    stopped: bool = False


@dataclass
class RunRecord:
    trace_id: str
    workflow: str
    identity: dict[str, str]
    model_calls: list[ModelCall] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    borders: list[dict[str, Any]] = field(default_factory=list)
    events: list[ModelCall | ToolCall] = field(default_factory=list)
    turns: int = 0
    outcome: str | None = None
    outcome_ref: str | None = None
    review_minutes: float = 0.0

    @property
    def model_usd(self) -> float:
        return sum(call.cost_usd for call in self.model_calls)

    @property
    def tool_usd(self) -> float:
        return sum(call.fee_usd for call in self.tool_calls)

    @property
    def repeats(self) -> int:
        return sum(call.repeat for call in self.tool_calls)

    @property
    def tokens(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.model_calls)


class Ledger(TracingProcessor):
    def __init__(self, card: PriceCard) -> None:
        self.card = card
        self.runs: dict[str, RunRecord] = {}

    def on_trace_start(self, trace: Any) -> None:
        seen = trace.export() or {}
        tags = seen.get("metadata") or {}
        identity = {
            key: str(tags.get(key, "unattributed")) for key in IDENTITY_KEYS
        }
        self.runs[trace.trace_id] = RunRecord(
            trace.trace_id, seen.get("workflow_name", ""), identity
        )

    def on_span_end(self, span: Any) -> None:
        run = self.runs.get(span.trace_id)
        seen = span.export() or {}
        data = seen.get("span_data") or {}
        if run is None:
            return
        if data.get("type") == "function":
            run.tool_calls.append(self._tool_call(run, data, seen.get("error")))
            run.events.append(run.tool_calls[-1])
        elif data.get("name") == "model_call" and "cost_usd" in data["data"]:
            fields = {
                key: data["data"][key] for key in ModelCall.__annotations__
            }
            run.model_calls.append(ModelCall(**fields))
            run.events.append(run.model_calls[-1])
        elif data.get("name") == "turn":
            run.turns += 1
        elif str(data.get("name", "")).startswith("border."):
            run.borders.append({"span": data["name"], **data["data"]})

    def label(
        self, trace_id: str, outcome: str, ref: str, review_minutes: float
    ) -> RunRecord:
        """Join the business outcome to the run. The approval flow calls this."""
        if outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {outcome!r}")
        run = self.runs[trace_id]
        run.outcome, run.outcome_ref = outcome, ref
        run.review_minutes = review_minutes
        return run

    def _tool_call(self, run: RunRecord, data: dict, error: Any) -> ToolCall:
        name, arguments = data["name"], data.get("input") or ""
        before = {(call.name, call.arguments) for call in run.tool_calls}
        refused = data.get("output") == REPEAT
        stopped = TRIPPED in str(error or "")
        ran = not (refused or stopped)
        return ToolCall(
            name,
            arguments,
            self.card.tool_fee(name) if ran else 0.0,
            failed=error is not None and not stopped,
            repeat=(name, arguments) in before,
            refused=refused,
            stopped=stopped,
        )

    def on_trace_end(self, trace: Any) -> None:
        pass

    def on_span_start(self, span: Any) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass
