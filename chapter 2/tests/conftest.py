import json
import sys
from pathlib import Path

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def json_message(payload: dict) -> object:
    return assistant_message(json.dumps(payload))


def scripted(*steps) -> ScriptedModel:
    return ScriptedModel(list(steps))


@pytest.fixture
def relevant_classifier():
    return scripted([json_message({"is_relevant": True, "reason": "An insurance claim."})])


@pytest.fixture
def off_topic_classifier():
    return scripted([json_message({"is_relevant": False, "reason": "Not an insurance matter."})])


def intake_script(is_complete: bool, missing: list[str]) -> ScriptedModel:
    return scripted(
        [
            function_call(
                "check_required_documents",
                {"claim_type": "property", "submitted_docs": ["photos"]},
                call_id="call_intake_1",
            )
        ],
        [
            json_message(
                {
                    "is_complete": is_complete,
                    "missing_documents": missing,
                    "claim_category": "property",
                    "priority": "standard",
                }
            )
        ],
    )


def review_script(verdict: dict) -> ScriptedModel:
    return scripted(
        [function_call("lookup_policy", {"policy_number": "HO-2024821"}, call_id="call_rev_1")],
        [
            function_call(
                "get_claim_history",
                {"policyholder_id": "PH-10021", "years": 3},
                call_id="call_rev_2",
            )
        ],
        [json_message(verdict)],
    )


def escalation_script() -> ScriptedModel:
    return scripted(
        [
            json_message(
                {
                    "summary": "Large fire loss needs a senior adjuster.",
                    "reasons": ["Amount above the autonomous limit."],
                    "recommended_action": "Assign to the large-loss desk.",
                }
            )
        ]
    )
