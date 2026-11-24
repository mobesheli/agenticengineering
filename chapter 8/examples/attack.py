"""Assume the model loses. Four runs on the patient whose record holds a hostile note.

    python -m examples.attack

Each scripted reader does exactly what the planted note asks, so the question in
every run is what the code around the model does next. No API key is needed.
"""

from __future__ import annotations

import asyncio

from agents import set_tracing_disabled

from chapter8.harness import Harness
from chapter8.phases import Parked, read_phase, request_write, resume_write
from examples import scripted
from examples.scripted import CLINICIAN

PATIENT = "pt-1002"


async def read_with(model: object, label: str) -> None:
    harness = Harness.build()
    session = harness.tokens.launch("read", CLINICIAN, PATIENT)
    outcome = await read_phase(harness.reader(model), session, harness.store)
    detail = "; ".join(outcome.problems)
    if outcome.status == "proposed" and outcome.proposal:
        reasons = [change.reason for change in outcome.proposal.changes]
        detail = "findings: " + ", ".join(reasons)
    print(label)
    print(f"    read phase {outcome.status}: {detail}")
    denied = harness.events.of_kind("policy_denied")
    print(
        f"    policy denials {len(denied)}, writes {len(harness.log.records())}"
    )


async def swapped_write() -> None:
    harness = Harness.build()
    session = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    outcome = await read_phase(
        harness.reader(scripted.reader_clean()), session, harness.store
    )
    assert outcome.proposal is not None
    writer = harness.writer(scripted.writer_adds_a_change(outcome.proposal))
    write_session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    parked = await request_write(
        writer, write_session, outcome.proposal, harness.store
    )
    assert isinstance(parked, Parked)
    review = harness.review(parked, CLINICIAN)
    signed = harness.approve(parked, CLINICIAN)
    final = await resume_write(
        writer, parked, write_session, harness.book, harness.clock()
    )
    print("writer adds a change the proposal did not contain")
    print(f"    review     {review.lines[-1].strip()}")
    print(f"    signature recorded: {'yes' if signed else 'no'}")
    print(f"    writer says: {final}")
    version = harness.store.version("pt-1001")
    print(
        f"    record version still {version}, writes {len(harness.log.records())}"
    )


async def run() -> None:
    await read_with(
        scripted.reader_resists(),
        "reader treats the note as data and reports it",
    )
    await read_with(
        scripted.reader_obeys_cross_patient(),
        "reader obeys the note and reaches for another patient",
    )
    await read_with(
        scripted.reader_obeys_discontinue(),
        "reader obeys the note and proposes stopping the warfarin",
    )
    await swapped_write()


def main() -> None:
    set_tracing_disabled(True)
    asyncio.run(run())


if __name__ == "__main__":
    main()
