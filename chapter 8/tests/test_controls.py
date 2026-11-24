"""The deterministic controls, one at a time."""

import copy
import threading

import pytest

from chapter8.approvals import action_hash
from chapter8.audit import Checkpoint
from chapter8.commit import Refused
from chapter8.linter import lint_approval_request
from chapter8.phases import read_phase
from chapter8.proposal import Change, Proposal, validate_proposal
from chapter8.records import Forbidden
from chapter8.redaction import fingerprint, scrub
from chapter8.responsible import Disclosure, outcome_rates, rate_ratio
from chapter8.stop import emergency_stop
from chapter8.threat import DESIGNS, autonomy_for
from examples import scripted
from examples.scripted import CLINICIAN

TOOL = "write_reconciliation"


async def proposal_for(harness, model=None):
    session = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    reader = harness.reader(model or scripted.reader_clean())
    outcome = await read_phase(reader, session, harness.store)
    return outcome.proposal, session


def signed(harness, arguments, approver=CLINICIAN):
    digest = action_hash(TOOL, arguments, "pt-1001")
    harness.book.grant(digest, approver, "clinician", harness.clock())
    return digest


def test_rule_of_two_flags_only_the_single_session():
    assert DESIGNS["one session"].held() == 3
    assert "split" in DESIGNS["one session"].verdict()
    assert DESIGNS["read phase"].held() == DESIGNS["write phase"].held() == 2
    assert autonomy_for("consequential-write") == "act with approval"
    assert autonomy_for("something new") == "advise"


def test_record_server_checks_the_token_itself(harness):
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    with pytest.raises(Forbidden, match="lacks patient/MedicationRequest.rs"):
        harness.store.read(session, "MedicationRequest")
    reader = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    with pytest.raises(Forbidden, match="lacks patient/MedicationRequest.u"):
        harness.store.update(reader, [])
    harness.clock.advance(minutes=6)
    with pytest.raises(Forbidden, match="expired or revoked"):
        harness.store.read(reader, "MedicationDispense")


def test_restricted_note_is_withheld_and_reads_are_audited(harness):
    session = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    notes = harness.store.read(session, "DocumentReference")
    withheld = [note for note in notes if "withheld" in note]
    assert len(withheld) == 1 and "text" not in withheld[0]
    event = harness.store.audit[0]
    assert event["resourceType"] == "AuditEvent" and event["action"] == "R"
    assert event["agent"][0]["requestor"] is True
    assert (
        event["agent"][1]["who"]["identifier"]["value"]
        == "reconciliation-reader"
    )


def test_action_hash_ignores_key_order_and_sees_every_edit():
    first = {"patient_id": "pt-1", "changes": [{"action": "add", "target": "x"}]}
    second = {
        "changes": [{"target": "x", "action": "add"}],
        "patient_id": "pt-1",
    }
    assert action_hash(TOOL, first, "pt-1") == action_hash(TOOL, second, "pt-1")
    edited = copy.deepcopy(first)
    edited["changes"][0]["target"] = "y"
    assert action_hash(TOOL, first, "pt-1") != action_hash(TOOL, edited, "pt-1")
    assert action_hash(TOOL, first, "pt-1") != action_hash(TOOL, first, "pt-2")
    assert action_hash(TOOL, first, "pt-1") != action_hash(
        "other", first, "pt-1"
    )


async def test_policy_rules(harness):
    proposal, _ = await proposal_for(harness)
    arguments = scripted.write_arguments(proposal)
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")

    def rule(tool=TOOL, args=arguments, version=7):
        return harness.policy.decide(session, tool, args, version)

    assert rule().rule == "no approval for this exact action"
    signed(harness, arguments)
    assert rule().allow
    assert rule(tool="export_records").rule == "unknown tool, denied by default"
    assert rule(version=8).rule == "record changed after the proposal was made"
    many = {**arguments, "changes": arguments["changes"] * 4}
    signed(harness, many)
    assert rule(args=many).rule == "too many changes in one write"
    harness.clock.advance(hours=25)
    assert rule().rule == "approval has expired"
    signed(harness, arguments, approver="Practitioner/dr-other")
    assert rule().rule == "approval is not from this clinician"
    harness.registry.stop(
        "reconciliation-writer", "test", "test", harness.clock()
    )
    assert rule().rule == "agent is stopped"


async def test_budget_holds_under_a_race(harness):
    proposal, _ = await proposal_for(harness)
    arguments = scripted.write_arguments(proposal)
    signed(harness, arguments)
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    harness.policy.limits.writes_per_hour = 3
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(
                harness.policy.authorize(session, TOOL, arguments, 7).allow
            )
        )
        for _ in range(40)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(results) == 3


async def test_commit_writes_two_linked_records_and_spends_the_approval(harness):
    proposal, _ = await proposal_for(harness)
    arguments = scripted.write_arguments(proposal)
    signed(harness, arguments)
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    reference = harness.committer.commit(session, TOOL, arguments)
    assert reference == "Patient/pt-1001/_history/8"
    first, second = harness.log.records()
    assert (first.kind, second.kind) == ("authorized", "executed")
    assert first.decision_id == second.decision_id
    assert (
        second.prev_hash == first.digest() and second.business_ref == reference
    )
    assert first.approver == CLINICIAN and first.principal == CLINICIAN
    assert "metoprolol" not in first.model_dump_json()
    with pytest.raises(Refused, match="no approval"):
        harness.committer.commit(session, TOOL, arguments)
    assert harness.log.records()[-1].kind == "denied"


async def test_commit_records_a_failure_at_the_record_server(harness):
    proposal, read_session = await proposal_for(harness)
    arguments = scripted.write_arguments(proposal)
    signed(harness, arguments)
    harness.catalog.agents["reconciliation-reader"].append(TOOL)
    with pytest.raises(Refused, match="lacks patient/MedicationRequest.u"):
        harness.committer.commit(read_session, TOOL, arguments)
    assert [r.kind for r in harness.log.records()] == ["authorized", "failed"]
    assert harness.store.version("pt-1001") == 7


def test_proposal_validation():
    session = type(
        "S", (), {"seen": {"MedicationRequest/a", "DocumentReference/n"}}
    )()

    def problems(*changes):
        proposal = Proposal(
            patient_id="p", record_version=1, changes=list(changes)
        )
        return validate_proposal(proposal, session)

    good = Change(
        action="discontinue",
        target="MedicationRequest/a",
        reason="duplicate_therapy",
        evidence=["MedicationRequest/a"],
    )
    assert problems(good) == []
    assert "appears twice" in problems(good, good)[0]
    unread = good.model_copy(update={"evidence": ["MedicationRequest/zzz"]})
    assert "did not read" in problems(unread)[0]
    note_only = good.model_copy(update={"evidence": ["DocumentReference/n"]})
    assert problems(note_only) == ["change 1 rests on a note alone"]
    wrong = good.model_copy(update={"action": "add"})
    assert "wrong kind" in problems(wrong)[0]


async def test_chain_detects_edits_drops_rewrites_and_forgery(harness):
    proposal, _ = await proposal_for(harness)
    arguments = scripted.write_arguments(proposal)
    signed(harness, arguments)
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    harness.committer.commit(session, TOOL, arguments)
    records = harness.log.records()
    mark = harness.notary.checkpoint(harness.log)
    assert harness.notary.verify(records, mark) == "intact"
    edited = [records[0].model_copy(update={"rule": "x"}), records[1]]
    assert harness.notary.verify(edited, mark) == "chain breaks at record 2"
    assert "missing" in harness.notary.verify(records[:1], mark)
    relinked = edited[1].model_copy(update={"prev_hash": edited[0].digest()})
    rewritten = [edited[0], relinked]
    assert "does not match the checkpoint" in harness.notary.verify(
        rewritten, mark
    )
    forged = Checkpoint(2, relinked.digest(), mark.signature)
    assert "signature" in harness.notary.verify(rewritten, forged)


def test_scrub_keeps_structure_and_fingerprints_content():
    span = {
        "object": "trace.span",
        "id": "span_1",
        "trace_id": "trace_1",
        "span_data": {
            "type": "function",
            "name": "read_notes",
            "output": "secret",
        },
        "error": {"message": "boom", "data": {"detail": "secret"}},
        "something_new": "secret",
    }
    clean = scrub(span, b"k")
    assert "secret" not in str(clean) and "something_new" not in clean
    assert clean["span_data"]["name"] == "read_notes"
    assert clean["span_data"]["output"]["chars"] == 6
    assert fingerprint("pt-1001", b"a") != fingerprint("pt-1001", b"b")
    assert fingerprint("pt-1001", b"a") == fingerprint("pt-1001", b"a")


def test_linter_flags_pressure_missing_items_and_long_narrative():
    assert lint_approval_request("Two changes listed below.", 2, 2, 200).clean
    soothing = lint_approval_request(
        "Routine, approve all, same as before.", 2, 2, 200
    )
    assert soothing.flags == [
        "blanket approval",
        "minimizing",
        "false precedent",
    ]
    assert "changes not itemized" in lint_approval_request("x", 12, 0, 200).flags
    assert (
        "narrative longer than evidence"
        in lint_approval_request("x" * 9, 1, 1, 5).flags
    )
    assert (
        "urgency" in lint_approval_request("Please sign ASAP", 1, 1, 200).flags
    )


async def test_emergency_stop_blocks_every_path(harness):
    session = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    report = emergency_stop(
        harness,
        ["reconciliation-reader", "reconciliation-writer"],
        "oncall",
        "drill",
    )
    assert report.tokens_revoked == 1
    with pytest.raises(Forbidden):
        harness.store.read(session, "MedicationRequest")
    fresh = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    outcome = await read_phase(
        harness.reader(scripted.reader_clean()), fresh, harness.store
    )
    assert outcome.status == "halted"
    assert harness.events.of_kind("agent_stopped")


def test_fairness_screen_and_disclosure():
    decisions = [("a", True)] * 8 + [("a", False)] * 2 + [("b", True)] * 5
    decisions += [("b", False)] * 5
    rates = outcome_rates(decisions)
    assert rates == {"a": 0.8, "b": 0.5}
    assert rate_ratio(rates) == pytest.approx(0.625)
    disclosure = Disclosure()
    assert disclosure.wrap("chat-1", "Hello").startswith(
        "You are talking to an AI"
    )
    assert disclosure.wrap("chat-1", "Again") == "Again"


def test_changed_tool_description_is_refused_at_load(harness):
    from chapter8.harness import CatalogMismatch

    assert harness.reader() is not None
    harness.catalog.tools["read_notes"].description_sha256 = "0" * 16
    with pytest.raises(CatalogMismatch, match="read_notes description changed"):
        harness.reader()
