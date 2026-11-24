"""The whole split session on the clean patient: read, review, sign, write.

python -m examples.reconcile --scripted    no API key needed
python -m examples.reconcile               live models, needs OPENAI_API_KEY
"""

from __future__ import annotations

import argparse
import asyncio

from agents import set_tracing_disabled

from chapter8.harness import Harness
from chapter8.phases import Parked, read_phase, request_write, resume_write
from examples import scripted
from examples.scripted import CLINICIAN

CLOSING = "Recorded as {reference}."


async def run(
    live: bool, patient: str = "pt-1001", show: bool = True
) -> Harness:
    say = print if show else (lambda *_: None)
    harness = Harness.build()
    session = harness.tokens.launch("read", CLINICIAN, patient)
    reader = harness.reader(None if live else scripted.reader_clean())
    outcome = await read_phase(reader, session, harness.store)
    say(f"read phase   {outcome.status}: {len(session.seen)} records read")
    if outcome.proposal is None or outcome.problems:
        say(f"             {'; '.join(outcome.problems)}")
        return harness
    say(
        f"             {len(outcome.proposal.changes)} changes proposed, all valid"
    )

    version = harness.store.version(patient) + 1
    closing = CLOSING.format(reference=f"Patient/{patient}/_history/{version}")
    model = None if live else scripted.writer_clean(outcome.proposal, closing)
    writer = harness.writer(model)
    write_session = harness.tokens.launch("write", CLINICIAN, patient)
    parked = await request_write(
        writer, write_session, outcome.proposal, harness.store
    )
    if not isinstance(parked, Parked):
        say(f"write phase  no write requested: {parked}")
        return harness
    say("write phase  paused for a signature")
    review = harness.review(parked, CLINICIAN)
    say("\n".join(review.lines))

    harness.clock.advance(minutes=40)
    harness.approve(parked, CLINICIAN)
    say(f"signature    {CLINICIAN}, 40 minutes later")
    fresh = harness.tokens.launch("write", CLINICIAN, patient)
    final = await resume_write(
        writer, parked, fresh, harness.book, harness.clock()
    )
    say(f"write phase  {final}")
    for record in harness.log.records():
        detail = record.business_ref or record.rule
        say(f"record       {record.decision_id} {record.kind:<11}{detail}")
    return harness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripted", action="store_true")
    arguments = parser.parse_args()
    set_tracing_disabled(True)
    asyncio.run(run(live=not arguments.scripted))


if __name__ == "__main__":
    main()
