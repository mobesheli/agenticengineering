import json

import pytest
from agents.testing import ScriptedModel, function_call

from claims_pipeline import agents as agent_defs
from claims_pipeline import guardrails
from claims_pipeline.data import SAMPLE_CLAIMS
from claims_pipeline.pipeline import process_claim
from tests.conftest import escalation_script, intake_script, json_message, review_script

APPROVE = {
    "decision": "approve",
    "confidence": 0.96,
    "cited_sections": ["Perils Insured Against", "Deductible"],
    "requires_human_review": False,
    "explanation": "A burst supply pipe is a sudden and accidental discharge.",
}


def wire(monkeypatch, *, classifier, intake=None, review=None, escalation=None):
    monkeypatch.setattr(guardrails.topic_classifier, "model", classifier)
    if intake is not None:
        monkeypatch.setattr(agent_defs.intake_agent, "model", intake)
    if review is not None:
        monkeypatch.setattr(agent_defs.claims_reviewer, "model", review)
    if escalation is not None:
        monkeypatch.setattr(agent_defs.escalation_agent, "model", escalation)


@pytest.mark.asyncio
async def test_off_topic_request_is_rejected_by_the_input_guardrail(
    monkeypatch, off_topic_classifier
):
    wire(monkeypatch, classifier=off_topic_classifier)
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4821"])
    assert outcome.status == "rejected"
    assert outcome.verdict is None
    assert outcome.trace_id.startswith("trace_")


@pytest.mark.asyncio
async def test_incomplete_claim_stops_after_intake(monkeypatch, relevant_classifier):
    wire(
        monkeypatch,
        classifier=relevant_classifier,
        intake=intake_script(False, ["contractor_estimate"]),
    )
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4822"])
    assert outcome.status == "incomplete"
    assert outcome.missing_documents == ["contractor_estimate"]


@pytest.mark.asyncio
async def test_confident_covered_claim_is_processed(monkeypatch, relevant_classifier):
    review = review_script(APPROVE)
    wire(
        monkeypatch,
        classifier=relevant_classifier,
        intake=intake_script(True, []),
        review=review,
    )
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4821"])
    assert outcome.status == "processed"
    assert outcome.verdict.decision == "approve"
    assert len(review.calls) == 3
    assert {tool.name for tool in review.calls[0].tools} == {"lookup_policy", "get_claim_history"}


@pytest.mark.asyncio
async def test_large_amount_escalates_regardless_of_model_confidence(
    monkeypatch, relevant_classifier
):
    wire(
        monkeypatch,
        classifier=relevant_classifier,
        intake=intake_script(True, []),
        review=review_script(APPROVE),
        escalation=escalation_script(),
    )
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4823"])
    assert outcome.status == "escalated"
    assert "exceeds" in outcome.reason
    assert outcome.report is not None


@pytest.mark.asyncio
async def test_decision_without_citation_trips_the_output_guardrail(
    monkeypatch, relevant_classifier
):
    uncited = dict(APPROVE, cited_sections=[])
    wire(
        monkeypatch,
        classifier=relevant_classifier,
        intake=intake_script(True, []),
        review=review_script(uncited),
    )
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4821"])
    assert outcome.status == "escalated"
    assert "without a policy citation" in outcome.reason


@pytest.mark.asyncio
async def test_turn_limit_falls_back_to_a_human_review_verdict(
    monkeypatch, relevant_classifier
):
    looping = ScriptedModel(
        [
            [function_call("lookup_policy", {"policy_number": "HO-2024821"}, call_id=f"c{i}")]
            for i in range(12)
        ]
    )
    wire(
        monkeypatch,
        classifier=relevant_classifier,
        intake=intake_script(True, []),
        review=looping,
        escalation=escalation_script(),
    )
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4821"])
    assert outcome.status == "escalated"
    assert outcome.verdict.decision == "investigate"
    assert "turn limit" in outcome.verdict.explanation


@pytest.mark.asyncio
async def test_history_tool_rejects_out_of_range_years(monkeypatch, relevant_classifier):
    review = ScriptedModel(
        [
            [
                function_call(
                    "get_claim_history",
                    {"policyholder_id": "PH-10021", "years": 20},
                    call_id="call_years",
                )
            ],
            [json_message(APPROVE)],
        ]
    )
    wire(
        monkeypatch,
        classifier=relevant_classifier,
        intake=intake_script(True, []),
        review=review,
    )
    outcome = await process_claim(SAMPLE_CLAIMS["CLM-4821"])
    assert outcome.status == "processed"
    second_call_input = json.dumps(review.calls[1].input, default=str)
    assert "Invalid range: years must be between 1 and 5" in second_call_input
    assert review.remaining_steps == 0
