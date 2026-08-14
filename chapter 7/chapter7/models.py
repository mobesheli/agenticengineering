"""Typed contracts shared by the Chapter 7 evaluation harness."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class TaskKind(str, Enum):
    GOLDEN = "golden"
    ABUSE = "abuse"


class GraderSpec(BaseModel):
    checks: list[str] = Field(min_length=1)
    judge_rubric: str | None = None


class EvalTask(BaseModel):
    task_id: str = Field(min_length=1)
    kind: TaskKind
    instruction: str = Field(min_length=1)
    fixtures: dict[str, str] = Field(min_length=1)
    expected: dict[str, str]
    grader: GraderSpec
    tags: list[str] = Field(default_factory=list)
    reference_solution: str = Field(min_length=1)

    @model_validator(mode="after")
    def expected_outcome_is_gradable(self) -> EvalTask:
        if "verdict" not in self.expected:
            raise ValueError("every task requires an expected verdict")
        return self


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Transcript(BaseModel):
    tool_calls: list[ToolCall] = Field(default_factory=list)
    rationale: str = ""
    cited_clauses: list[str] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    model_cost: float = Field(default=0.0, ge=0)
    latency_seconds: float = Field(default=0.0, ge=0)

    def rationale_with_citations(self) -> str:
        citations = ", ".join(self.cited_clauses) or "none"
        return f"Rationale: {self.rationale}\nCited clauses: {citations}"


class Trial(BaseModel):
    task_id: str
    task_kind: TaskKind
    index: int = Field(ge=0)
    transcript: Transcript
    final_state: dict[str, Any]


class TrialGrade(BaseModel):
    task_id: str
    index: int
    passed: bool
    failures: list[str] = Field(default_factory=list)
    judge_passed: bool | None = None


class CalibrationReport(BaseModel):
    sample_size: int = Field(gt=0)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    agreement: float = Field(ge=0, le=1)
    cohens_kappa: float = Field(ge=-1, le=1)


class SuiteResult(BaseModel):
    run_id: str
    trial_count: int = Field(ge=0)
    task_count: int = Field(ge=0)
    k: int = Field(ge=1)
    quality_mean: float = Field(ge=0, le=1)
    quality_se: float = Field(ge=0)
    golden_pass_rate: float = Field(ge=0, le=1)
    abuse_pass_rate: float = Field(ge=0, le=1)
    pass_at_k: float = Field(ge=0, le=1)
    pass_to_k: float = Field(ge=0, le=1)
    cost_per_task: float = Field(ge=0)
    latency_p50: float = Field(ge=0)
    latency_p95: float = Field(ge=0)
    artifacts: dict[str, Any] = Field(default_factory=dict)


GateStatus = Literal["ok", "warn", "block"]


class GateVerdict(BaseModel):
    status: GateStatus
    reasons: list[str] = Field(default_factory=list)

    @property
    def allows_deployment(self) -> bool:
        return self.status != "block"
