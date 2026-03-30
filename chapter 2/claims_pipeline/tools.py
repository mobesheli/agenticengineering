from __future__ import annotations

from agents import function_tool

from .data import get_claim, get_claim_history_records, get_policy, required_documents_for


@function_tool
def check_required_documents(claim_id: str) -> str:
    """Check whether a claim has the documents required for the incident type."""
    claim = get_claim(claim_id)
    required_documents = required_documents_for(claim.incident_type)
    missing_documents = sorted(set(required_documents) - set(claim.submitted_documents))
    if missing_documents:
        missing = ", ".join(missing_documents)
        return f"Missing documents for {claim_id}: {missing}."
    return f"Claim {claim_id} includes every required document."


@function_tool
def lookup_policy(policy_number: str, section: str | None = None) -> str:
    """Look up a sample insurance policy and optionally return one section."""
    policy = get_policy(policy_number)
    if section:
        section_text = policy.sections.get(section)
        if not section_text:
            return f"Section {section} was not found for policy {policy_number}."
        return f"{section}: {section_text}"

    section_names = ", ".join(sorted(policy.sections))
    return (
        f"Policy {policy.policy_number} has deductible {policy.deductible}, "
        f"coverage limit {policy.coverage_limit}, and sections: {section_names}."
    )


@function_tool
def get_claim_history(policyholder_id: str, years: int = 3) -> str:
    """Return the small sample claims history used by the chapter demo."""
    history = get_claim_history_records(policyholder_id)
    if not history:
        return f"No claims found for {policyholder_id} in the last {years} years."
    return "\n".join(history)
