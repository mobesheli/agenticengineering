"""The split session end to end, with scripted models that behave and misbehave."""

from chapter8.phases import Parked, read_phase, request_write, resume_write
from examples import scripted
from examples.scripted import CLINICIAN


async def read(harness, model, patient):
    session = harness.tokens.launch("read", CLINICIAN, patient)
    outcome = await read_phase(harness.reader(model), session, harness.store)
    return outcome, session


async def parked_write(harness, writer_model=None):
    outcome, _ = await read(harness, scripted.reader_clean(), "pt-1001")
    model = writer_model or scripted.writer_clean(outcome.proposal, "Recorded.")
    writer = harness.writer(model)
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    parked = await request_write(
        writer, session, outcome.proposal, harness.store
    )
    return writer, session, parked


async def test_clean_run_reads_proposes_pauses_and_writes(harness):
    writer, _, parked = await parked_write(harness)
    assert isinstance(parked, Parked) and not parked.asks[0].problem
    assert harness.store.version("pt-1001") == 7
    review = harness.review(parked, CLINICIAN)
    assert review.approvable and review.lint.clean
    assert harness.approve(parked, CLINICIAN)
    harness.clock.advance(minutes=40)
    fresh = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    final = await resume_write(
        writer, parked, fresh, harness.book, harness.clock()
    )
    assert final == "Recorded."
    assert harness.store.version("pt-1001") == 8
    stopped = harness.store._patients["pt-1001"].medications[3]
    assert (
        stopped.status == "stopped"
        and len(harness.store._patients["pt-1001"].flags) == 2
    )
    added = harness.store._patients["pt-1001"].medications[4]
    assert added.name == "aspirin" and added.status == "active"
    assert [r.kind for r in harness.log.records()] == ["authorized", "executed"]


async def test_nothing_is_written_without_a_signature(harness):
    writer, session, parked = await parked_write(harness)
    await resume_write(writer, parked, session, harness.book, harness.clock())
    assert harness.store.version("pt-1001") == 7
    assert harness.log.records() == []


async def test_parked_state_holds_no_session(harness):
    _, session, parked = await parked_write(harness)
    assert session.token_id not in parked.state
    assert CLINICIAN not in parked.state


async def test_resume_on_the_expired_session_halts_at_the_guardrail(harness):
    import pytest
    from agents.exceptions import ToolInputGuardrailTripwireTriggered

    writer, session, parked = await parked_write(harness)
    harness.approve(parked, CLINICIAN)
    harness.clock.advance(minutes=40)
    with pytest.raises(ToolInputGuardrailTripwireTriggered):
        await resume_write(
            writer, parked, session, harness.book, harness.clock()
        )
    assert harness.store.version("pt-1001") == 7


async def test_reader_that_resists_reports_the_planted_instruction(harness):
    outcome, _ = await read(harness, scripted.reader_resists(), "pt-1002")
    reasons = [change.reason for change in outcome.proposal.changes]
    assert outcome.status == "proposed"
    assert reasons == ["allergy_conflict", "embedded_instruction"]


async def test_reader_that_obeys_cannot_reach_another_patient(harness):
    outcome, session = await read(
        harness, scripted.reader_obeys_cross_patient(), "pt-1002"
    )
    assert outcome.status == "halted"
    assert outcome.problems == ["not this session's patient"]
    assert not any("mr-901" in record for record in session.seen)
    assert len(harness.events.of_kind("policy_denied")) == 1


async def test_reader_that_obeys_cannot_get_a_note_only_change_through(harness):
    outcome, _ = await read(
        harness, scripted.reader_obeys_discontinue(), "pt-1002"
    )
    assert outcome.status == "invalid"
    assert outcome.problems == ["change 1 rests on a note alone"]


async def test_writer_that_adds_a_change_cannot_be_approved(harness):
    outcome, _ = await read(harness, scripted.reader_clean(), "pt-1001")
    model = scripted.writer_adds_a_change(outcome.proposal)
    writer, session, parked = await parked_write(harness, model)
    assert "differs" in parked.asks[0].problem
    assert not harness.review(parked, CLINICIAN).approvable
    assert harness.approve(parked, CLINICIAN) is False
    await resume_write(writer, parked, session, harness.book, harness.clock())
    assert harness.store.version("pt-1001") == 7


async def test_writer_input_carries_no_note_text(harness):
    from chapter8.phases import write_input

    outcome, _ = await read(harness, scripted.reader_clean(), "pt-1001")
    packet = write_input(outcome.proposal, harness.store)
    assert "bottles" not in packet and "evidence" not in packet
    assert "metoprolol tartrate 25 mg twice daily" in packet
