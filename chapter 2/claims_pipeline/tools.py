"""Function tools that give the agents access to the insurer's systems."""

from agents import function_tool

from .data import REQUIRED_DOCS, db, format_claims_summary
from .settings import MAX_HISTORY_YEARS, TOOL_TIMEOUT_SECONDS


@function_tool(
    timeout=TOOL_TIMEOUT_SECONDS,
    timeout_behavior="error_as_result",
)
async def lookup_policy(
    policy_number: str,
    section: str | None = None,
) -> str:
    """Look up an insurance policy by number.

    Returns the full policy summary or a specific section.
    Policy numbers use the format XX-XXXXXXX, for example HO-2024821.
    """
    policy = await db.get_policy(policy_number)
    if not policy:
        return (
            f"No policy found for {policy_number}. "
            "Verify the number format: XX-XXXXXXX."
        )
    if section:
        return policy.get_section(section)
    return policy.summary()


@function_tool(
    timeout=TOOL_TIMEOUT_SECONDS,
    timeout_behavior="error_as_result",
)
async def get_claim_history(
    policyholder_id: str,
    years: int = 3,
) -> str:
    """Retrieve claims history for a policyholder.

    Returns prior claims within the requested number of years.
    Use this to check for patterns or prior similar claims.
    Do not request more than 5 years of history.
    """
    if not 1 <= years <= MAX_HISTORY_YEARS:
        return (
            f"Invalid range: years must be between 1 and {MAX_HISTORY_YEARS}. "
            f"You requested {years}."
        )
    claims = await db.get_claims(policyholder_id, years=years)
    return format_claims_summary(claims)


@function_tool
async def check_required_documents(
    claim_type: str,
    submitted_docs: list[str],
) -> str:
    """Check whether all required documents for a claim are present.

    Returns the list of missing documents, or confirms the claim is complete.
    Claim types: property, auto, liability, workers_comp.
    """
    required = REQUIRED_DOCS.get(claim_type)
    if required is None:
        known = ", ".join(REQUIRED_DOCS)
        return f"Unknown claim type '{claim_type}'. Known types: {known}."
    missing = [doc for doc in required if doc not in submitted_docs]
    if not missing:
        return "All required documents are present."
    return f"Missing documents: {', '.join(missing)}"
