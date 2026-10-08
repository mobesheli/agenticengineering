"""Typed contracts for the Chapter 10 deployment companion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GateMode = Literal["monitor", "comment", "block"]
Route = Literal["build", "join", "assemble", "buy"]
RiskTier = Literal["low", "medium", "high"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderModelPin(StrictModel):
    id: str = Field(min_length=1)
    effort: str | None = None
    processing: str | None = None
    golden_pass: float | None = Field(default=None, ge=0, le=1)
    floor: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def fallback_has_gate_result(self) -> ProviderModelPin:
        if (self.golden_pass is None) != (self.floor is None):
            raise ValueError("golden_pass and floor must be supplied together")
        return self


class ModelRoutes(StrictModel):
    primary: ProviderModelPin
    fallback: ProviderModelPin


class MemorySchema(StrictModel):
    version: int = Field(ge=1)
    reads: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def current_version_is_readable(self) -> MemorySchema:
        if self.version not in self.reads:
            raise ValueError("memory schema must be able to read its current version")
        return self


class ReleaseBundle(StrictModel):
    bundle: str = Field(min_length=1)
    image: str = Field(pattern=r"^.+@sha256:[0-9a-f]{64}$")
    prompts: str = Field(min_length=1)
    tool_catalog: str = Field(min_length=1)
    policy_pack: str = Field(min_length=1)
    sandbox: str = Field(pattern=r"^.+@sha256:[0-9a-f]{64}$")
    model: ModelRoutes
    memory_schema: MemorySchema
    eval_suite: str = Field(min_length=1)

    @model_validator(mode="after")
    def immutable_references_only(self) -> ReleaseBundle:
        for field_name in ("prompts", "tool_catalog", "policy_pack", "eval_suite"):
            value = getattr(self, field_name)
            if "@" not in value:
                raise ValueError(f"{field_name} must carry an immutable version")
        fallback = self.model.fallback
        if fallback.golden_pass is None or fallback.floor is None:
            raise ValueError("fallback model must carry its golden-set result")
        if fallback.golden_pass < fallback.floor:
            raise ValueError("fallback model has not earned release eligibility")
        return self


class ToolContract(StrictModel):
    tool: str = Field(min_length=1)
    server: str = Field(min_length=1)
    version: str = Field(min_length=1)
    allow: list[str] = Field(min_length=1)
    never: list[str] = Field(default_factory=list)
    egress: list[str] = Field(min_length=1)
    credential: Literal["agent-identity"]

    @model_validator(mode="after")
    def permissions_are_unambiguous(self) -> ToolContract:
        overlap = set(self.allow) & set(self.never)
        if overlap:
            raise ValueError(f"operations cannot be both allowed and denied: {overlap}")
        if len(set(self.allow)) != len(self.allow):
            raise ValueError("allowed operations must be unique")
        return self


class EvaluationReport(StrictModel):
    suite: str = Field(min_length=1)
    bundle: str = Field(min_length=1)
    passed: int = Field(ge=0)
    total: int = Field(gt=0)
    floor: float = Field(ge=0, le=1)
    trials_per_case: int = Field(default=1, ge=1)
    required_case_trials_passed: int = Field(default=1, ge=0)
    cache_enabled: bool = False
    tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def counts_are_possible(self) -> EvaluationReport:
        if self.passed > self.total:
            raise ValueError("passed cannot exceed total")
        if self.required_case_trials_passed > self.trials_per_case:
            raise ValueError("required case successes cannot exceed its trials")
        return self

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total

    @property
    def required_pass_k(self) -> bool:
        return self.required_case_trials_passed == self.trials_per_case


class GateDecision(StrictModel):
    mode: GateMode
    verdict: Literal["pass", "warn", "block"]
    enforced: bool
    candidate_rate: float = Field(ge=0, le=1)
    baseline_rate: float = Field(ge=0, le=1)
    candidate_interval: tuple[float, float]
    baseline_interval: tuple[float, float]
    reasons: list[str] = Field(default_factory=list)


class PipelineStage(StrictModel):
    name: str
    passed: bool
    detail: str


class PipelineReport(StrictModel):
    bundle: str
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: GateMode
    passed: bool
    stages: list[PipelineStage]
    gate: GateDecision
    created_at: datetime


class Budget(StrictModel):
    monthly_usd: float = Field(gt=0)
    source: Literal["metered", "allocated"]


class ValueLine(StrictModel):
    claim: str = Field(min_length=1)
    stage: Literal["declared", "baselined", "measured", "validated"]


class AgentEntry(StrictModel):
    agent: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    route: Route
    tier: RiskTier
    status: Literal[
        "registered",
        "identified",
        "connected",
        "gated",
        "live",
        "listed",
        "steady",
        "contracted",
        "suspended",
    ]
    bundle: str = Field(min_length=1)
    budget: Budget
    evidence: dict[str, str] = Field(default_factory=dict)
    value_line: ValueLine
    drift: dict[str, str | float | int | None] = Field(default_factory=dict)


class ListingResult(StrictModel):
    agent: str
    accepted: bool
    missing: list[str] = Field(default_factory=list)


class IntakeRequest(StrictModel):
    name: str
    purpose: str
    audience: str
    reviewer: str
    data_tier: RiskTier
    workflow_kind: Literal["company-specific", "commodity"]
    needs_internal_inspection: bool = True


class IntakeRecommendation(StrictModel):
    route: Literal["reuse", "buy", "build"]
    reason: str
    match: str | None = None
    scaffold: dict[str, Any] | None = None


class ParkedRun(StrictModel):
    run_id: str
    bundle: str
    state: dict[str, Any]
    idempotency_key: str
    parked_at: datetime


class ResumeResult(StrictModel):
    status: Literal["resumed", "stale", "rejected"]
    run_id: str
    reason: str | None = None
    state: dict[str, Any] | None = None


class KillSwitch(StrictModel):
    name: Literal["gateway", "identity", "contract", "runtime", "register", "data"]
    owner: str
    backup: str
    stops: str
    target: str
    active: bool = False


class DrillResult(StrictModel):
    switch: str
    target: str
    active: bool
    elapsed_ms: int = Field(ge=0)
