from __future__ import annotations

from agents import Agent, InputGuardrail, OutputGuardrail

from .guardrails import check_topic_relevance, require_citations_and_valid_confidence
from .models import ClaimVerdict, EscalationReport, IntakeResult
from .tools import check_required_documents, get_claim_history, lookup_policy

DEFAULT_MODEL = "gpt-4.1-mini"


def build_claims_intake_agent(model: str = DEFAULT_MODEL) -> Agent:
    return Agent(
        name="claims_intake",
        model=model,
        instructions=(
            "You are a claims intake specialist. "
            "Use the document-checking tool, decide whether the claim is complete, "
            "and return a short structured answer."
        ),
        tools=[check_required_documents],
        output_type=IntakeResult,
        input_guardrails=[
            InputGuardrail(
                guardrail_function=check_topic_relevance,
                name="claim_topic_check",
                run_in_parallel=False,
            )
        ],
    )


def build_claims_reviewer_agent(model: str = DEFAULT_MODEL) -> Agent:
    return Agent(
        name="claims_reviewer",
        model=model,
        instructions=(
            "You are a senior claims reviewer. "
            "Use the policy and claims history tools when needed. "
            "Always cite the policy section that supports your decision."
        ),
        tools=[lookup_policy, get_claim_history],
        output_type=ClaimVerdict,
        output_guardrails=[
            OutputGuardrail(
                guardrail_function=require_citations_and_valid_confidence,
                name="claim_verdict_check",
            )
        ],
    )


def build_claims_escalation_agent(model: str = DEFAULT_MODEL) -> Agent:
    return Agent(
        name="claims_escalation",
        model=model,
        instructions=(
            "You are a claims escalation coordinator. "
            "Summarize why a claim needs a human reviewer and recommend the next action."
        ),
        output_type=EscalationReport,
    )


def build_policy_advisor_agent(model: str = DEFAULT_MODEL) -> Agent:
    return Agent(
        name="policy_advisor",
        model=model,
        instructions=(
            "Answer policy questions using the policy lookup tool. "
            "Keep your explanation short and reference the policy section when possible."
        ),
        tools=[lookup_policy],
        output_type=str,
    )


def build_router_agent(model: str = DEFAULT_MODEL) -> Agent:
    reviewer = build_claims_reviewer_agent(model=model)
    policy_advisor = build_policy_advisor_agent(model=model)
    return Agent(
        name="claims_router",
        model=model,
        instructions=(
            "Route insurance claim review work to the claims reviewer. "
            "Route general policy questions to the policy advisor."
        ),
        handoffs=[reviewer, policy_advisor],
    )
