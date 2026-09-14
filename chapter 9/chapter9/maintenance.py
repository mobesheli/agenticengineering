"""Deterministic maintenance-agent run that emits priced, outcome-labeled traces."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .budget import BudgetExhausted, LoopDetected, RunBudget
from .models import MaintenanceCase, NormalizedUsage, TraceIdentity, TraceRecord
from .pricing import load_price_card, price_model_usage
from .tracing import InMemoryLedger, new_span

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "fixtures" / "maintenance_cases.json"
BASELINE_PATH = ROOT / "data" / "baselines" / "human_work_orders_v1.json"
REVIEW_RATE_PER_MINUTE = 0.98


def load_cases(path: Path = CASES_PATH) -> list[MaintenanceCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [MaintenanceCase.model_validate(row) for row in payload]


def load_baselines(path: Path = BASELINE_PATH) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in payload["by_severity"].items()}


class MaintenanceHarness:
    """Offline workflow whose telemetry is the product of the run, not a fixture."""

    def __init__(
        self,
        *,
        ledger: InMemoryLedger | None = None,
        price_card: Any = None,
        baselines: dict[str, float] | None = None,
    ) -> None:
        self.ledger = ledger or InMemoryLedger()
        self.price_card = price_card or load_price_card()
        self.baselines = baselines or load_baselines()

    def run_all(self, cases: list[MaintenanceCase] | None = None) -> list[TraceRecord]:
        return [self.run_case(case) for case in (cases or load_cases())]

    def run_case(self, case: MaintenanceCase) -> TraceRecord:
        day = int(case.case_id[-3:])
        started_at = datetime.fromisoformat(
            f"{case.period}-01T08:00:00+00:00"
        ) + timedelta(
            days=day - 1,
            minutes=sum(ord(ch) for ch in case.plant) % 37,
        )
        identity = TraceIdentity(
            tenant="heavy-things-manufacturing",
            plant=case.plant,
            principal=f"planner-{case.plant[-1].lower()}-042",
            agent_version="9.0.0",
            prompt_bundle="maintenance-v3-sha256:7e53f8",
            tool_catalog_version="maintenance-tools-v2",
        )
        trace = self.ledger.start_trace(
            trace_id=f"trace-{case.case_id.lower()}",
            identity=identity,
            severity=case.severity,
            period=case.period,
            baseline_usd=self.baselines[case.severity],
            started_at=started_at,
        )
        limit = (
            0.005
            if case.force_budget_stop
            else {
                "routine": 0.35,
                "major": 0.65,
                "critical": 0.90,
            }[case.severity]
        )
        budget = RunBudget(
            price_card=self.price_card,
            limit_usd=limit,
            max_calls=12,
            max_steps=12,
            max_seconds=30,
        )
        root = new_span(
            trace_id=trace.trace_id,
            kind="agent",
            name="maintenance_planning",
            started_at=started_at,
            duration_ms=0,
            direct_cost_usd=self.price_card.trace_span,
            attributes=identity.model_dump(),
        )
        self.ledger.append_span(trace.trace_id, root)
        cursor = started_at + timedelta(milliseconds=10)

        try:
            cursor = self._generation(
                trace.trace_id,
                root.span_id,
                cursor,
                step="plan",
                model="maintenance-mid"
                if case.severity == "routine"
                else "maintenance-frontier",
                usage=self._plan_usage(case.severity),
                budget=budget,
            )
            cursor = self._tool(
                trace.trace_id,
                root.span_id,
                cursor,
                "read_sensor_summary",
                {"asset_id": case.asset_id, "sensor_code": case.sensor_code},
                budget,
            )
            cursor = self._tool(
                trace.trace_id,
                root.span_id,
                cursor,
                "read_repair_history",
                {"asset_id": case.asset_id, "limit": 8},
                budget,
            )
            cursor = self._generation(
                trace.trace_id,
                root.span_id,
                cursor,
                step="read_results",
                model="maintenance-small",
                usage=NormalizedUsage(
                    input_tokens=20_000,
                    cached_input_tokens=15_000,
                    output_tokens=500,
                    reasoning_tokens=100,
                ),
                budget=budget,
            )
            parts_args = {"asset_id": case.asset_id, "fault_code": case.sensor_code}
            cursor = self._tool(
                trace.trace_id,
                root.span_id,
                cursor,
                "check_parts_catalog",
                parts_args,
                budget,
            )
            if case.repeat_parts_lookup:
                try:
                    cursor = self._tool(
                        trace.trace_id,
                        root.span_id,
                        cursor,
                        "check_parts_catalog",
                        parts_args,
                        budget,
                    )
                except LoopDetected as exc:
                    span = new_span(
                        trace_id=trace.trace_id,
                        parent_id=root.span_id,
                        kind="guardrail",
                        name="loop_breaker",
                        step_type="tool_selection",
                        started_at=cursor,
                        duration_ms=0.2,
                        status="denied",
                        direct_cost_usd=self.price_card.trace_span,
                        attributes={"reason": "loop", "detail": str(exc)},
                    )
                    self.ledger.append_span(trace.trace_id, span)
                    cursor += timedelta(milliseconds=1)
            cursor = self._generation(
                trace.trace_id,
                root.span_id,
                cursor,
                step="synthesis",
                model="maintenance-mid",
                usage=NormalizedUsage(
                    input_tokens=25_000,
                    cached_input_tokens=18_000,
                    output_tokens=1_200,
                    reasoning_tokens=300,
                ),
                budget=budget,
            )
            self._tool(
                trace.trace_id,
                root.span_id,
                cursor,
                "write_draft_work_order",
                {"case_id": case.case_id, "proposal_only": True},
                budget,
            )
        except BudgetExhausted as exc:
            budget.record_stop(budget.stop_reason or "budget_exhausted")
            span = new_span(
                trace_id=trace.trace_id,
                parent_id=root.span_id,
                kind="guardrail",
                name="run_budget",
                started_at=cursor,
                duration_ms=0.2,
                status="stopped",
                direct_cost_usd=self.price_card.trace_span,
                attributes={
                    "reason": budget.stop_reason,
                    "detail": str(exc),
                    **budget.snapshot(),
                },
            )
            self.ledger.append_span(trace.trace_id, span)
            self.ledger.label_outcome(
                trace.trace_id,
                outcome="stopped",
                outcome_ref=None,
                review_minutes=0,
                review_rate_per_minute=REVIEW_RATE_PER_MINUTE,
                stop_reason=budget.stop_reason,
            )
            return self.ledger.get(trace.trace_id)

        outcome_ref = (
            f"WO-{case.case_id}" if case.outcome in {"approved", "edited"} else None
        )
        self.ledger.label_outcome(
            trace.trace_id,
            outcome=case.outcome,
            outcome_ref=outcome_ref,
            review_minutes=case.review_minutes,
            review_rate_per_minute=REVIEW_RATE_PER_MINUTE,
            stop_reason=budget.stop_reason,
        )
        return self.ledger.get(trace.trace_id)

    def _generation(
        self,
        trace_id: str,
        parent_id: str,
        cursor: datetime,
        *,
        step: str,
        model: str,
        usage: NormalizedUsage,
        budget: RunBudget,
    ) -> datetime:
        cost = price_model_usage(usage, model=model, card=self.price_card)
        reservation = budget.reserve_model(model, usage)
        budget.settle(reservation, cost.total)
        duration = {
            "plan": 1_850,
            "read_results": 620,
            "synthesis": 1_120,
        }[step]
        span = new_span(
            trace_id=trace_id,
            parent_id=parent_id,
            kind="generation",
            name=f"model.{step}",
            step_type=step,
            model=model,
            started_at=cursor,
            duration_ms=duration,
            usage=usage,
            cost=cost,
            direct_cost_usd=self.price_card.trace_span,
            attributes={"price_card_version": self.price_card.version},
        )
        self.ledger.append_span(trace_id, span)
        return cursor + timedelta(milliseconds=duration + 20)

    def _tool(
        self,
        trace_id: str,
        parent_id: str,
        cursor: datetime,
        tool_name: str,
        arguments: dict[str, Any],
        budget: RunBudget,
    ) -> datetime:
        direct_cost = self.price_card.tool_cost(tool_name)
        reservation = budget.reserve_tool(tool_name, arguments)
        budget.settle(reservation, direct_cost)
        duration = {
            "read_sensor_summary": 85,
            "read_repair_history": 110,
            "check_parts_catalog": 140,
            "write_draft_work_order": 25,
        }[tool_name]
        span = new_span(
            trace_id=trace_id,
            parent_id=parent_id,
            kind="tool",
            name=f"tool.{tool_name}",
            step_type="tool_call",
            tool_name=tool_name,
            arguments=arguments,
            started_at=cursor,
            duration_ms=duration,
            direct_cost_usd=direct_cost + self.price_card.trace_span,
            attributes={"attempt": 1, "price_card_version": self.price_card.version},
        )
        self.ledger.append_span(trace_id, span)
        return cursor + timedelta(milliseconds=duration + 10)

    @staticmethod
    def _plan_usage(severity: str) -> NormalizedUsage:
        if severity == "routine":
            return NormalizedUsage(
                input_tokens=10_000,
                cached_input_tokens=7_000,
                output_tokens=800,
                reasoning_tokens=400,
            )
        if severity == "major":
            return NormalizedUsage(
                input_tokens=18_000,
                cached_input_tokens=12_000,
                output_tokens=1_500,
                reasoning_tokens=1_000,
            )
        return NormalizedUsage(
            input_tokens=24_000,
            cached_input_tokens=15_000,
            output_tokens=2_100,
            reasoning_tokens=1_500,
        )
