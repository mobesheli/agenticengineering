from __future__ import annotations

from datetime import datetime, timezone

import pytest

from chapter8.audit import DecisionChain, DecisionRecord, audit_event
from chapter8.responsible import DisclosureMiddleware, four_fifths_check

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def record(record_id: str, prev_hash: str) -> DecisionRecord:
    return DecisionRecord(
        record_id=record_id,
        prev_hash=prev_hash,
        trace_id="trace-1",
        principal="Practitioner/42",
        delegation_chain=["Practitioner/42", "agent"],
        agent_id="agent",
        agent_version="8.0.0",
        model_id="deterministic-reader",
        policy_bundle_version="policy-1",
        tool_name="write_reconciliation",
        args_hash="a" * 64,
        policy_decision="allow",
        policy_rule="approved write within budget",
        recorded_at=NOW,
    )


def test_decision_chain_verifies_and_detects_tampering() -> None:
    chain = DecisionChain()
    first = record("decision-1", chain.head_hash)
    chain.append(first)
    chain.append(record("decision-2", chain.head_hash))
    assert chain.verify() is True
    chain._records[0].policy_rule = "altered"
    assert chain.verify() is False


def test_public_decision_records_are_defensive_copies() -> None:
    chain = DecisionChain()
    chain.append(record("decision-1", chain.head_hash))
    exported = chain.records[0]
    exported.policy_rule = "changed outside"
    assert chain.verify() is True
    assert chain.records[0].policy_rule == "approved write within budget"


def test_fhir_audit_event_names_human_and_software_participants() -> None:
    event = audit_event(
        "agent-1",
        "Practitioner/42",
        "Patient/synthetic-1",
        "C",
        "MedicationRequest/1",
        "0",
        recorded_at=NOW,
    )
    assert event["resourceType"] == "AuditEvent"
    assert event["agent"][0]["requestor"] is True
    assert event["agent"][1]["requestor"] is False
    assert event["entity"][1]["what"]["reference"] == "MedicationRequest/1"


def test_four_fifths_rule_is_a_tripwire_not_a_verdict() -> None:
    report = four_fifths_check(
        [("group-a", True)] * 8
        + [("group-a", False)] * 2
        + [("group-b", True)] * 6
        + [("group-b", False)] * 4
    )
    assert report.outcome_rates == {"group-a": 0.8, "group-b": 0.6}
    assert report.selection_ratio == pytest.approx(0.75)
    assert report.passes is False


def test_disclosure_is_injected_only_on_first_turn() -> None:
    middleware = DisclosureMiddleware()
    first = middleware.first_turn("web-1", "How can I help?")
    second = middleware.first_turn("web-1", "What would you like to review?")
    assert first.startswith("You are interacting with an AI agent.")
    assert second == "What would you like to review?"
