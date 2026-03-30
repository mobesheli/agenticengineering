from __future__ import annotations

import json

from agents import RunConfig, Runner, trace

from .agents import (
    DEFAULT_MODEL,
    build_claims_escalation_agent,
    build_claims_intake_agent,
    build_claims_reviewer_agent,
)
from .data import (
    build_claim_input,
    get_claim,
    get_claim_history_records,
    get_policy,
    required_documents_for,
)
from .models import ClaimRecord, ClaimVerdict, EscalationReport, IntakeResult, PipelineResult


def build_intake_result(claim: ClaimRecord) -> IntakeResult:
    required = required_documents_for(claim.incident_type)
    missing_documents = sorted(set(required) - set(claim.submitted_documents))
    return IntakeResult(
        claim_id=claim.claim_id,
        is_complete=not missing_documents,
        missing_documents=missing_documents,
        next_step="review" if not missing_documents else "request_documents",
    )


def build_offline_verdict(claim: ClaimRecord) -> ClaimVerdict:
    policy = get_policy(claim.policy_number)

    if claim.incident_type not in policy.covered_incidents:
        return ClaimVerdict(
            claim_id=claim.claim_id,
            decision="denied",
            confidence=0.97,
            cited_sections=["SECTION_Z_EXCLUSIONS"],
            requires_human_review=False,
            explanation="The incident type is not covered by the sample policy.",
        )

    cited_section = policy.covered_incidents[claim.incident_type]
    unusual_pattern = _requires_manual_review(claim)

    if unusual_pattern:
        return ClaimVerdict(
            claim_id=claim.claim_id,
            decision="needs_human_review",
            confidence=0.66,
            cited_sections=[cited_section, "SECTION_C_ESCALATION"],
            requires_human_review=True,
            explanation=(
                "The claim is covered, but the amount or claims history pushes it to human review."
            ),
        )

    return ClaimVerdict(
        claim_id=claim.claim_id,
        decision="approved",
        confidence=0.92,
        cited_sections=[cited_section],
        requires_human_review=False,
        explanation="The claim is covered and the sample risk checks are within tolerance.",
    )


def _requires_manual_review(claim: ClaimRecord) -> bool:
    policy = get_policy(claim.policy_number)
    claim_history = get_claim_history_records(claim.policyholder_id)
    return claim.amount > policy.coverage_limit or len(claim_history) >= 3


def _enforce_manual_review_rules(claim: ClaimRecord, verdict: ClaimVerdict) -> ClaimVerdict:
    if not _requires_manual_review(claim):
        return verdict

    cited_sections = list(verdict.cited_sections)
    if "SECTION_C_ESCALATION" not in cited_sections:
        cited_sections.append("SECTION_C_ESCALATION")

    return ClaimVerdict(
        claim_id=verdict.claim_id,
        decision="needs_human_review",
        confidence=min(verdict.confidence, 0.66),
        cited_sections=cited_sections,
        requires_human_review=True,
        explanation=(
            "The claim may be covered, but deterministic business rules require human review "
            "because the amount or the claims history is outside the automatic approval path."
        ),
    )


def build_escalation_report(claim: ClaimRecord, verdict: ClaimVerdict) -> EscalationReport:
    reason = (
        f"{claim.claim_id} needs human review because the amount is {claim.amount} "
        f"or the claims pattern is unusual."
    )
    action = (
        f"Assign {claim.claim_id} to a senior reviewer and verify documents against "
        f"{', '.join(verdict.cited_sections)}."
    )
    return EscalationReport(
        claim_id=claim.claim_id,
        reason=reason,
        recommended_action=action,
    )


def run_offline_pipeline(claim_id: str) -> PipelineResult:
    claim = get_claim(claim_id)
    intake = build_intake_result(claim)
    if not intake.is_complete:
        return PipelineResult(
            claim_id=claim.claim_id,
            stage="request_documents",
            intake=intake,
        )

    verdict = build_offline_verdict(claim)
    if verdict.requires_human_review:
        escalation = build_escalation_report(claim, verdict)
        return PipelineResult(
            claim_id=claim.claim_id,
            stage="escalated",
            intake=intake,
            verdict=verdict,
            escalation=escalation,
        )

    return PipelineResult(
        claim_id=claim.claim_id,
        stage="review_complete",
        intake=intake,
        verdict=verdict,
    )


async def run_live_pipeline(
    claim_id: str,
    model: str = DEFAULT_MODEL,
) -> PipelineResult:
    claim = get_claim(claim_id)
    claim_input = build_claim_input(claim)
    intake_agent = build_claims_intake_agent(model=model)
    reviewer_agent = build_claims_reviewer_agent(model=model)
    escalation_agent = build_claims_escalation_agent(model=model)
    run_config = RunConfig(
        workflow_name="chapter_2_claims_pipeline",
        trace_include_sensitive_data=False,
    )

    with trace("chapter_2_claims_pipeline"):
        intake_run = await Runner.run(
            intake_agent,
            claim_input,
            max_turns=5,
            run_config=run_config,
        )
        intake = intake_run.final_output

        if not intake.is_complete:
            return PipelineResult(
                claim_id=claim.claim_id,
                stage="request_documents",
                intake=intake,
            )

        reviewer_run = await Runner.run(
            reviewer_agent,
            claim_input,
            max_turns=7,
            run_config=run_config,
        )
        verdict = _enforce_manual_review_rules(claim, reviewer_run.final_output)

        if verdict.requires_human_review:
            escalation_input = (
                f"Claim input:\n{claim_input}\n\n"
                f"Claim verdict:\n{json.dumps(verdict.model_dump(), indent=2)}"
            )
            escalation_run = await Runner.run(
                escalation_agent,
                escalation_input,
                max_turns=5,
                run_config=run_config,
            )
            return PipelineResult(
                claim_id=claim.claim_id,
                stage="escalated",
                intake=intake,
                verdict=verdict,
                escalation=escalation_run.final_output,
            )

        return PipelineResult(
            claim_id=claim.claim_id,
            stage="review_complete",
            intake=intake,
            verdict=verdict,
        )
