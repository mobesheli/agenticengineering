from __future__ import annotations

from .models import ClaimRecord, PolicyRecord

REQUIRED_DOCUMENTS: dict[str, list[str]] = {
    "water_damage": ["claim_form", "photos", "repair_estimate"],
    "theft": ["claim_form", "police_report", "inventory_list"],
    "fire": ["claim_form", "fire_report", "photos", "repair_estimate"],
}

POLICIES: dict[str, PolicyRecord] = {
    "POL-1001": PolicyRecord(
        policy_number="POL-1001",
        policyholder_id="CUST-100",
        covered_incidents={"water_damage": "SECTION_A_WATER"},
        sections={
            "SECTION_A_WATER": (
                "Water damage is covered when it is sudden, accidental, and documented."
            ),
            "SECTION_Z_EXCLUSIONS": (
                "Gradual wear and long-term neglect are not covered."
            ),
        },
        deductible=1000.0,
        coverage_limit=25000.0,
    ),
    "POL-2002": PolicyRecord(
        policy_number="POL-2002",
        policyholder_id="CUST-200",
        covered_incidents={"theft": "SECTION_B_THEFT"},
        sections={
            "SECTION_B_THEFT": (
                "Theft is covered when a police report and an inventory list are provided."
            ),
            "SECTION_Z_EXCLUSIONS": (
                "Losses without supporting evidence can be denied."
            ),
        },
        deductible=500.0,
        coverage_limit=15000.0,
    ),
    "POL-3003": PolicyRecord(
        policy_number="POL-3003",
        policyholder_id="CUST-300",
        covered_incidents={"water_damage": "SECTION_A_WATER"},
        sections={
            "SECTION_A_WATER": (
                "Water damage is covered when caused by a sudden event inside the coverage limit."
            ),
            "SECTION_C_ESCALATION": (
                "Claims with unusual severity or repeated loss patterns must be reviewed by a human."
            ),
        },
        deductible=1500.0,
        coverage_limit=12000.0,
    ),
}

CLAIMS: dict[str, ClaimRecord] = {
    "CLM-1001": ClaimRecord(
        claim_id="CLM-1001",
        policy_number="POL-1001",
        policyholder_id="CUST-100",
        incident_type="water_damage",
        amount=6200.0,
        date_of_loss="2026-01-15",
        submitted_documents=["claim_form", "photos", "repair_estimate"],
        summary="Basement water damage caused by a burst pipe.",
    ),
    "CLM-1002": ClaimRecord(
        claim_id="CLM-1002",
        policy_number="POL-2002",
        policyholder_id="CUST-200",
        incident_type="theft",
        amount=3200.0,
        date_of_loss="2026-02-02",
        submitted_documents=["claim_form", "inventory_list"],
        summary="Garage theft with missing police report.",
    ),
    "CLM-1003": ClaimRecord(
        claim_id="CLM-1003",
        policy_number="POL-3003",
        policyholder_id="CUST-300",
        incident_type="water_damage",
        amount=18000.0,
        date_of_loss="2026-03-04",
        submitted_documents=["claim_form", "photos", "repair_estimate"],
        summary="Large kitchen flood after an appliance failure.",
    ),
}

CLAIM_HISTORY: dict[str, list[str]] = {
    "CUST-100": ["2024 wind damage claim, resolved and paid."],
    "CUST-200": [],
    "CUST-300": [
        "2024 water damage claim, resolved and paid.",
        "2025 pipe freeze claim, resolved and paid.",
        "2025 roof leak claim, resolved and paid.",
    ],
}


def list_claim_ids() -> list[str]:
    return sorted(CLAIMS)


def get_claim(claim_id: str) -> ClaimRecord:
    if claim_id not in CLAIMS:
        raise KeyError(f"Unknown claim id: {claim_id}")
    return CLAIMS[claim_id]


def get_policy(policy_number: str) -> PolicyRecord:
    if policy_number not in POLICIES:
        raise KeyError(f"Unknown policy number: {policy_number}")
    return POLICIES[policy_number]


def get_claim_history_records(policyholder_id: str) -> list[str]:
    return CLAIM_HISTORY.get(policyholder_id, [])


def required_documents_for(incident_type: str) -> list[str]:
    return REQUIRED_DOCUMENTS.get(incident_type, ["claim_form"])


def build_claim_input(claim: ClaimRecord) -> str:
    submitted_documents = ", ".join(claim.submitted_documents)
    return (
        f"Claim ID: {claim.claim_id}\n"
        f"Policy number: {claim.policy_number}\n"
        f"Policyholder id: {claim.policyholder_id}\n"
        f"Incident type: {claim.incident_type}\n"
        f"Date of loss: {claim.date_of_loss}\n"
        f"Amount: {claim.amount}\n"
        f"Submitted documents: {submitted_documents}\n"
        f"Summary: {claim.summary}"
    )
