from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from chapter8.evidence import emit_security_evidence, verify_manifest
from chapter8.identity import clinician_read_session, clinician_write_session
from chapter8.reconciliation import (
    QuarantinedReader,
    SyntheticRecordStore,
    load_fixture,
)
from chapter8.registry import AgentStoppedError
from chapter8.runtime import SecurityHarness

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
CLINICIAN = "Practitioner/42"


def read_session(patient_id: str):
    return clinician_read_session(
        clinician_ref=CLINICIAN,
        patient_id=patient_id,
        now=NOW,
        trace_id="trace-test",
    )


def write_session(patient_id: str):
    return clinician_write_session(
        clinician_ref=CLINICIAN,
        patient_id=patient_id,
        now=NOW,
        trace_id="trace-test",
    )


def approved_run(fixture_name: str = "hostile_note"):
    patient = load_fixture(fixture_name)
    harness = SecurityHarness(patient, clock=lambda: NOW)
    proposal = harness.propose(read_session(patient.patient_id))
    grant = harness.approve(
        proposal,
        approver=CLINICIAN,
        approver_role="clinician",
        narrative="Review the itemized changes and evidence.",
    )
    session = write_session(patient.patient_id)
    session.approvals[grant.action_hash] = grant
    return harness, proposal, session


def test_hostile_note_changes_detector_signal_not_structured_clinical_result() -> None:
    clean = load_fixture("clean")
    hostile = load_fixture("hostile_note")
    clean_reader = QuarantinedReader(SyntheticRecordStore([clean]))
    hostile_reader = QuarantinedReader(SyntheticRecordStore([hostile]))
    clean_proposal = clean_reader.build_proposal(clean.patient_id, now=NOW)
    hostile_proposal = hostile_reader.build_proposal(hostile.patient_id, now=NOW)
    assert clean_proposal.changes == hostile_proposal.changes
    assert clean_proposal.detector_flags == []
    assert len(hostile_proposal.detector_flags) == 3
    serialized = hostile_proposal.model_dump_json()
    assert "Ignore previous" not in serialized
    assert "outside service" not in serialized


def test_read_phase_cannot_write() -> None:
    patient = load_fixture("hostile_note")
    store = SyntheticRecordStore([patient])
    proposal = QuarantinedReader(store).build_proposal(patient.patient_id, now=NOW)
    assert proposal.changes
    assert store.writes == ()


def test_commit_without_approval_is_denied_and_recorded() -> None:
    patient = load_fixture("clean")
    harness = SecurityHarness(patient, clock=lambda: NOW)
    proposal = harness.propose(read_session(patient.patient_id))
    outcome = harness.commit(proposal, write_session=write_session(patient.patient_id))
    assert outcome.status == "denied"
    assert "no approval" in outcome.policy_rule
    assert harness.store.writes == ()
    assert harness.decisions.verify() is True


def test_approved_commit_writes_once_and_emits_joined_audit_records() -> None:
    harness, proposal, session = approved_run()
    outcome = harness.commit(proposal, write_session=session)
    assert outcome.status == "committed"
    assert len(harness.store.writes) == 1
    assert outcome.business_record_ref == harness.store.writes[0]["record_ref"]
    assert outcome.audit_event["entity"][1]["what"]["reference"] == outcome.business_record_ref
    assert harness.decisions.records[-1].business_record_ref == outcome.business_record_ref
    assert harness.decisions.verify() is True


def test_approval_for_one_proposal_cannot_authorize_a_changed_proposal() -> None:
    harness, proposal, session = approved_run("clean")
    proposal.changes[0].reason_code = "changed_after_approval"
    outcome = harness.commit(proposal, write_session=session)
    assert outcome.status == "denied"
    assert "no approval" in outcome.policy_rule


def test_cross_patient_write_is_denied_before_record_change() -> None:
    harness, proposal, _ = approved_run("clean")
    outcome = harness.commit(
        proposal,
        write_session=write_session("synthetic-patient-002"),
    )
    assert outcome.status == "denied"
    assert outcome.policy_rule == "cross-patient write attempt"
    assert harness.store.writes == ()


def test_stop_control_blocks_next_action_and_restore_is_external() -> None:
    patient = load_fixture("clean")
    harness = SecurityHarness(patient, clock=lambda: NOW)
    harness.stop("operator stop")
    with pytest.raises(AgentStoppedError, match="operator stop"):
        harness.propose(read_session(patient.patient_id))
    harness.registry.restore(harness.agent_id)
    assert harness.propose(read_session(patient.patient_id)).patient_id == patient.patient_id


def test_privacy_canary_hashes_notes_and_removes_personal_values() -> None:
    patient = load_fixture("hostile_note")
    harness = SecurityHarness(patient, clock=lambda: NOW)
    report = harness.privacy_canary_report()
    assert report["passed"] is True
    assert report["leaks"] == []
    assert report["redacted_sample"]["notes"][0]["text"].startswith("sha256:")


def test_evidence_pack_verifies_and_stop_test_leaves_agent_enabled(tmp_path) -> None:
    harness, proposal, session = approved_run()
    outcome = harness.commit(proposal, write_session=session)
    manifest = emit_security_evidence(harness, outcome, tmp_path / "evidence")
    assert verify_manifest(manifest) is True
    assert harness.registry.require_enabled(harness.agent_id).enabled is True
    assert (manifest.parent / "stop_control.json").exists()
    assert (manifest.parent / "privacy_canary.json").exists()


def test_expired_session_fails_closed() -> None:
    patient = load_fixture("clean")
    later = NOW + timedelta(minutes=6)
    harness = SecurityHarness(patient, clock=lambda: later)
    with pytest.raises(PermissionError, match="expired"):
        harness.propose(read_session(patient.patient_id))
