"""Typed contracts shared by the Chapter 9 companion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ModelRates(BaseModel):
    """Illustrative USD rates per million tokens."""

    input: float = Field(ge=0)
    cached_input: float = Field(ge=0)
    cache_write: float = Field(ge=0)
    output: float = Field(ge=0)


class PriceCard(BaseModel):
    version: str = Field(min_length=1)
    effective_at: datetime
    currency: Literal["USD"] = "USD"
    illustrative: bool = True
    models: dict[str, ModelRates] = Field(min_length=1)
    tools: dict[str, float] = Field(default_factory=dict)
    trace_span: float = Field(default=0.0, ge=0)

    def rates_for(self, model: str) -> ModelRates:
        try:
            return self.models[model]
        except KeyError as exc:
            raise KeyError(
                f"model {model!r} is missing from price card {self.version}; "
                "unknown models fail closed"
            ) from exc

    def tool_cost(self, tool_name: str) -> float:
        try:
            return self.tools[tool_name]
        except KeyError as exc:
            raise KeyError(
                f"tool {tool_name!r} is missing from price card {self.version}; "
                "unknown tools fail closed"
            ) from exc


class NormalizedUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def token_subsets_fit_totals(self) -> NormalizedUsage:
        if self.cached_input_tokens + self.cache_write_tokens > self.input_tokens:
            raise ValueError(
                "cached and cache-write tokens cannot exceed total input tokens"
            )
        if self.reasoning_tokens > self.output_tokens:
            raise ValueError("reasoning tokens cannot exceed total output tokens")
        return self

    @property
    def uncached_input_tokens(self) -> int:
        return self.input_tokens - self.cached_input_tokens - self.cache_write_tokens

    @property
    def visible_output_tokens(self) -> int:
        return self.output_tokens - self.reasoning_tokens


class TurnCost(BaseModel):
    uncached_input: float = Field(default=0.0, ge=0)
    cached_input: float = Field(default=0.0, ge=0)
    cache_write: float = Field(default=0.0, ge=0)
    reasoning: float = Field(default=0.0, ge=0)
    visible_output: float = Field(default=0.0, ge=0)

    @property
    def total(self) -> float:
        return sum(
            (
                self.uncached_input,
                self.cached_input,
                self.cache_write,
                self.reasoning,
                self.visible_output,
            )
        )


class TraceIdentity(BaseModel):
    tenant: str = Field(min_length=1)
    plant: str = Field(min_length=1)
    principal: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    prompt_bundle: str = Field(min_length=1)
    tool_catalog_version: str = Field(min_length=1)
    workflow: str = "maintenance_planning"
    environment: str = "offline-demo"
    owner: str = "maintenance-platform-team"


SpanKind = Literal["agent", "generation", "tool", "guardrail", "handoff", "border"]


class SpanRecord(BaseModel):
    span_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    parent_id: str | None = None
    kind: SpanKind
    name: str = Field(min_length=1)
    step_type: str | None = None
    model: str | None = None
    tool_name: str | None = None
    arguments_hash: str | None = None
    status: Literal["ok", "error", "denied", "stopped"] = "ok"
    started_at: datetime
    duration_ms: float = Field(default=0.0, ge=0)
    usage: NormalizedUsage | None = None
    cost: TurnCost | None = None
    direct_cost_usd: float = Field(default=0.0, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def cost_usd(self) -> float:
        return (self.cost.total if self.cost else 0.0) + self.direct_cost_usd


OutcomeLabel = Literal[
    "approved", "edited", "rejected", "escalated", "abandoned", "stopped"
]


class TraceRecord(BaseModel):
    trace_id: str = Field(min_length=1)
    identity: TraceIdentity
    started_at: datetime
    spans: list[SpanRecord] = Field(default_factory=list)
    severity: Literal["routine", "major", "critical"]
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    outcome: OutcomeLabel | None = None
    outcome_ref: str | None = None
    review_minutes: float = Field(default=0.0, ge=0)
    review_rate_per_minute: float = Field(default=0.0, ge=0)
    baseline_usd: float = Field(gt=0)
    stop_reason: str | None = None

    @property
    def machine_cost_usd(self) -> float:
        return sum(span.cost_usd for span in self.spans)

    @property
    def human_cost_usd(self) -> float:
        return self.review_minutes * self.review_rate_per_minute

    @property
    def fully_loaded_cost_usd(self) -> float:
        return self.machine_cost_usd + self.human_cost_usd

    @property
    def approved(self) -> bool:
        return self.outcome == "approved"


class MaintenanceCase(BaseModel):
    case_id: str = Field(min_length=1)
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    plant: Literal["Plant A", "Plant B", "Plant C", "Plant D"]
    severity: Literal["routine", "major", "critical"]
    sensor_code: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    outcome: OutcomeLabel
    review_minutes: float = Field(ge=0)
    repeat_parts_lookup: bool = False
    force_budget_stop: bool = False


class PlantValueRow(BaseModel):
    plant: str
    severity: str
    attempts: int = Field(ge=0)
    successes: int = Field(ge=0)
    success_rate: float = Field(ge=0, le=1)
    ci_95_low: float = Field(ge=0, le=1)
    ci_95_high: float = Field(ge=0, le=1)
    cost_per_outcome_usd: float | None = Field(default=None, ge=0)
    baseline_usd: float = Field(gt=0)
    verdict: Literal["below baseline", "above baseline", "no outcomes"]


class RoutingCandidate(BaseModel):
    name: str
    model: str
    effort: Literal["low", "medium", "high"]
    quality: float = Field(ge=0, le=1)
    cost_per_outcome_usd: float = Field(gt=0)
