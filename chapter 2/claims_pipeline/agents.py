"""Agent definitions for the claims pipeline and the handoff example."""

from agents import Agent, InputGuardrail, OutputGuardrail

from .guardrails import enforce_citations, reject_non_insurance
from .models import ClaimVerdict, EscalationReport, IntakeResult
from .settings import MODELS
from .tools import check_required_documents, get_claim_history, lookup_policy

INTAKE_INSTRUCTIONS = (
    "You are a claims intake specialist at a property and casualty "
    "insurer. Use the document check tool to confirm that the claim "
    "has every required document, then categorize the claim by type "
    "and priority. Mark a claim urgent only when the description "
    "indicates ongoing damage or a safety risk."
)

REVIEW_INSTRUCTIONS = (
    "You are a senior insurance claims reviewer at a mid-size property "
    "and casualty insurer. Your role is to evaluate submitted claims "
    "against policy terms.\n\n"
    "For each claim, perform these steps:\n"
    "1. Look up the policy and identify the applicable sections\n"
    "2. Check the policyholder's claims history for patterns\n"
    "3. Decide: approve when the policy was in force, the loss matches "
    "a covered peril, no exclusion applies, and the documents support "
    "it; deny when an exclusion clearly applies; investigate only when "
    "the evidence is insufficient\n"
    "4. Flag anything unusual for human review\n\n"
    "Never approve a claim without citing the specific policy section. "
    "Report your confidence as a number between 0.0 and 1.0."
)

ESCALATION_INSTRUCTIONS = (
    "You are a claims escalation coordinator. Prepare a concise summary "
    "for a human reviewer covering the original claim, the automated "
    "assessment, and the specific reasons the claim was escalated. "
    "Recommend one concrete next action."
)

intake_agent = Agent(
    name="claims_intake",
    model=MODELS.fast,
    instructions=INTAKE_INSTRUCTIONS,
    tools=[check_required_documents],
    output_type=IntakeResult,
    input_guardrails=[
        InputGuardrail(
            guardrail_function=reject_non_insurance,
            name="reject_non_insurance",
            run_in_parallel=False,
        ),
    ],
)

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=REVIEW_INSTRUCTIONS,
    tools=[lookup_policy, get_claim_history],
    output_type=ClaimVerdict,
    output_guardrails=[
        OutputGuardrail(
            guardrail_function=enforce_citations,
            name="enforce_citations",
        ),
    ],
)

escalation_agent = Agent(
    name="claims_escalation",
    model=MODELS.review,
    instructions=ESCALATION_INSTRUCTIONS,
    output_type=EscalationReport,
)

policy_advisor = Agent(
    name="policy_advisor",
    model=MODELS.review,
    instructions=(
        "You answer questions about policy coverage, exclusions, and "
        "renewal terms. Use the policy lookup tool and cite the policy "
        "section for every answer."
    ),
    tools=[lookup_policy],
)

triage_agent = Agent(
    name="triage",
    model=MODELS.fast,
    instructions=(
        "You are an insurance triage agent. Classify incoming requests "
        "and route them to the appropriate specialist. For claims, hand "
        "off to the claims reviewer. For policy questions, hand off to "
        "the policy advisor."
    ),
    handoffs=[claims_reviewer, policy_advisor],
)
