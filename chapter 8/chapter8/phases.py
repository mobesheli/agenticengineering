"""The split session: a read phase, a pause for a signature, and a write phase."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from agents import Agent, Runner, RunState
from agents.exceptions import (
    AgentsException,
    ToolInputGuardrailTripwireTriggered,
)
from pydantic import ValidationError

from chapter8.approvals import ApprovalBook, action_hash
from chapter8.proposal import (
    Proposal,
    WriteArguments,
    build_proposal,
    same_changes,
    validate_proposal,
)
from chapter8.records import RecordStore
from chapter8.session import Session
from chapter8.settings import READER_TURNS, WRITER_TURNS

READ_PROMPT = "Reconcile the medication list for patient {patient}."
TOOL = "write_reconciliation"


@dataclass
class ReadOutcome:
    status: str
    proposal: Proposal | None
    problems: list[str]


async def read_phase(
    reader: Agent[Session], session: Session, store: RecordStore
) -> ReadOutcome:
    prompt = READ_PROMPT.format(patient=session.patient_id)
    try:
        result = await Runner.run(
            reader, prompt, context=session, max_turns=READER_TURNS
        )
    except ToolInputGuardrailTripwireTriggered as halt:
        return ReadOutcome("halted", None, [halt.output.output_info["reason"]])
    except AgentsException as error:
        return ReadOutcome("failed", None, [type(error).__name__])
    proposal = build_proposal(result.final_output, session, store)
    problems = validate_proposal(proposal, session)
    return ReadOutcome("invalid" if problems else "proposed", proposal, problems)


@dataclass
class Ask:
    arguments: WriteArguments | None
    digest: str
    problem: str


@dataclass
class Parked:
    state: str
    proposal: Proposal
    asks: list[Ask]


def write_input(proposal: Proposal, store: RecordStore) -> str:
    """What the writer sees: codes and structured fields. No note text gets here."""
    changes = []
    for change in proposal.changes:
        item = store.medication(proposal.patient_id, change.target)
        label = f"{item.name} {item.dose}" if item else change.target
        row = change.model_dump(exclude={"evidence"})
        changes.append({**row, "medication": label})
    packet = proposal.model_dump(exclude={"changes"})
    return json.dumps({**packet, "changes": changes})


def as_ask(raw: str | None, proposal: Proposal, session: Session) -> Ask:
    try:
        arguments = WriteArguments.model_validate_json(raw or "")
    except ValidationError:
        return Ask(None, "", "the write arguments are not valid")
    digest = action_hash(TOOL, arguments.model_dump(), session.patient_id)
    if not same_changes(proposal, arguments):
        return Ask(
            arguments, digest, "the write differs from the validated proposal"
        )
    return Ask(arguments, digest, "")


async def request_write(
    writer: Agent[Session],
    session: Session,
    proposal: Proposal,
    store: RecordStore,
) -> Parked | str:
    packet = write_input(proposal, store)
    result = await Runner.run(
        writer, packet, context=session, max_turns=WRITER_TURNS
    )
    if not result.interruptions:
        return str(result.final_output)
    asks = [
        as_ask(item.arguments, proposal, session)
        for item in result.interruptions
    ]
    state = result.to_state().to_string(context_serializer=lambda _: {})
    return Parked(state, proposal, asks)


async def resume_write(
    writer: Agent[Session],
    parked: Parked,
    session: Session,
    book: ApprovalBook,
    now: datetime,
) -> str:
    state = await RunState.from_string(
        writer, parked.state, context_override=session
    )
    for item in state.get_interruptions():
        ask = as_ask(item.arguments, parked.proposal, session)
        problem = ask.problem or book.problem(
            ask.digest, session.clinician, "clinician", now
        )
        if problem:
            state.reject(
                item, rejection_message=f"Refused: {problem}. Do not retry."
            )
        else:
            state.approve(item)
    result = await Runner.run(writer, state, max_turns=WRITER_TURNS)
    return str(result.final_output)
