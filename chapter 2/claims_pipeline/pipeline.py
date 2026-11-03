"""Deterministic orchestration around three agents.

The model reasons inside each stage. Python owns the control flow between
stages and enforces the business thresholds, so a verdict never leaves
this function without passing the rules in rules.py.
"""

from agents import RunConfig, Runner, trace
from agents.exceptions import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from agents.run_error_handlers import RunErrorHandlerInput
from agents.tracing import gen_trace_id

from .agents import claims_reviewer, escalation_agent, intake_agent
from .models import Claim, ClaimVerdict, EscalationReport, IntakeResult, PipelineOutcome
from .rules import escalation_reasons, needs_escalation
from .settings import INTAKE_MAX_TURNS, REVIEW_MAX_TURNS


def fallback_verdict(data: RunErrorHandlerInput) -> ClaimVerdict:
    return ClaimVerdict(
        decision="investigate",
        confidence=0.0,
        cited_sections=[],
        requires_human_review=True,
        explanation=(
            "The reviewer reached its turn limit before producing a verdict. "
            "A human reviewer must assess this claim."
        ),
    )


def build_run_config() -> RunConfig:
    return RunConfig(trace_include_sensitive_data=False)


async def process_claim(claim: Claim) -> PipelineOutcome:
    trace_id = gen_trace_id()
    config = build_run_config()
    with trace(
        "claim_processing",
        trace_id=trace_id,
        metadata={"claim_ref": claim.claim_id},
    ):
        try:
            intake_run = await Runner.run(
                intake_agent,
                claim.as_text(),
                max_turns=INTAKE_MAX_TURNS,
                run_config=config,
            )
        except InputGuardrailTripwireTriggered:
            return PipelineOutcome(
                status="rejected",
                claim_id=claim.claim_id,
                trace_id=trace_id,
                reason="The request is not an insurance claim.",
            )
        intake: IntakeResult = intake_run.final_output
        if not intake.is_complete:
            return PipelineOutcome(
                status="incomplete",
                claim_id=claim.claim_id,
                trace_id=trace_id,
                missing_documents=intake.missing_documents,
            )

        try:
            review_run = await Runner.run(
                claims_reviewer,
                claim.as_text(),
                max_turns=REVIEW_MAX_TURNS,
                run_config=config,
                error_handlers={"max_turns": fallback_verdict},
            )
        except OutputGuardrailTripwireTriggered:
            return PipelineOutcome(
                status="escalated",
                claim_id=claim.claim_id,
                trace_id=trace_id,
                reason="Decision without a policy citation.",
            )
        verdict: ClaimVerdict = review_run.final_output

        if needs_escalation(verdict, claim.amount_usd):
            reasons = escalation_reasons(verdict, claim.amount_usd)
            escalation_run = await Runner.run(
                escalation_agent,
                build_escalation_input(claim, verdict, reasons),
                run_config=config,
            )
            report: EscalationReport = escalation_run.final_output
            return PipelineOutcome(
                status="escalated",
                claim_id=claim.claim_id,
                trace_id=trace_id,
                reason=" ".join(reasons),
                verdict=verdict,
                report=report,
            )

        return PipelineOutcome(
            status="processed",
            claim_id=claim.claim_id,
            trace_id=trace_id,
            verdict=verdict,
        )


def build_escalation_input(claim: Claim, verdict: ClaimVerdict, reasons: list[str]) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in reasons)
    return (
        f"Original claim:\n{claim.as_text()}\n\n"
        f"Automated assessment:\n{verdict.model_dump_json(indent=2)}\n\n"
        f"Escalation reasons:\n{reason_lines}"
    )
