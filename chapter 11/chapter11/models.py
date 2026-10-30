"""Typed contracts shared by the Chapter 11 exercises."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Rate = Annotated[float, Field(ge=0, le=1)]
Rung = Annotated[int, Field(ge=0, le=4)]
Signal = Literal["model", "input", "knowledge", "outcome", "cost_speed"]
SIGNALS = ("model", "input", "knowledge", "outcome", "cost_speed")


class Record(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, validate_assignment=True
    )


class RunConfiguration(Record):
    model: str = Field(min_length=1)
    reasoning_effort: str = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    prompt_version: str
    safety_layer: str
    route: str
    tool_interface: str
    memory_schema: int = Field(ge=1)
    memory_writer: str


class Reading(Record):
    signal: Signal
    value: float = Field(ge=0)
    baseline: float = Field(ge=0)
    band: float = Field(ge=0)
    absolute_band: float = Field(default=0, ge=0)

    @property
    def moved(self) -> bool:
        return (
            abs(self.value - self.baseline)
            > max(self.absolute_band, self.band * self.baseline) + 1e-12
        )


class AgentEntry(Record):
    agent: str
    owner: str
    sponsor: str | None
    attested_day: int | None = Field(default=None, ge=0)
    attestation_days: int = Field(default=90, gt=0)
    tier: Literal["low", "medium", "high"]
    rung: Rung
    ceiling: Rung
    bundle: str
    status: Literal["live", "suspended", "deprecated", "retired"] = "live"
    purpose: str
    retirement_trigger: str
    always_approve: list[str] = Field(default_factory=list)
    allow_actions: list[str] = Field(default_factory=list)
    consumers: list[str] = Field(default_factory=list)
    contract_version: int = Field(default=1, ge=1)
    cost_per_outcome: float = Field(default=1, gt=0)
    drift: dict[Signal, str] = Field(default_factory=dict)
    drift_hold_active: bool = False

    @model_validator(mode="after")
    def within_ceiling(self) -> AgentEntry:
        if self.rung > self.ceiling:
            raise ValueError("rung exceeds this agent's ceiling")
        return self

    def sponsored(self, day: int) -> bool:
        return bool(
            self.sponsor
            and self.attested_day is not None
            and 0 <= day - self.attested_day < self.attestation_days
        )


class PromotionEvidence(Record):
    bundle: str
    observed_days: int = Field(ge=0)
    trials: list[list[bool]]
    planted_caught: int = Field(ge=0)
    planted_total: int = Field(gt=0)
    cost_in_band: bool
    days_since_incident: int = Field(ge=0)
    exception_rate_stable: bool = False
    reviewer_miss_rate: Rate | None = None
    review_cadence_met: bool = False
    unreviewed_irreversible_actions: int = Field(default=0, ge=0)
    drill_age_days: int | None = Field(default=None, ge=0)
    finance_controls: bool = False

    @model_validator(mode="after")
    def possible_counts(self) -> PromotionEvidence:
        if self.planted_caught > self.planted_total:
            raise ValueError("caught checks exceed planted checks")
        return self


class PromotionRule(Record):
    source: Rung
    target: Rung
    window_days: int = Field(ge=1)
    k: int = Field(ge=1)
    min_pass_k: Rate
    min_catch_rate: Rate
    incident_free_days: int = Field(ge=0)
    signer_roles: list[str] = Field(min_length=1)
    max_reviewer_miss_rate: Rate = 0.05
    consecutive_denials: int = Field(default=3, gt=0)
    shift_denials: int = Field(default=20, gt=0)

    @model_validator(mode="after")
    def one_step(self) -> PromotionRule:
        if self.target != self.source + 1:
            raise ValueError("promotion rules must advance exactly one rung")
        return self


class Approval(Record):
    role: str
    name: str = Field(min_length=1)
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class Event(Record):
    event_id: str
    day: int = Field(ge=0, le=365)
    title: str
    kind: Literal[
        "note", "drift", "drop", "promotion", "release", "attest", "sponsor_left"
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
