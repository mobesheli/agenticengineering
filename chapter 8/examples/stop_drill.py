"""The emergency stop, drilled: one write lands, then the stop is pressed.

python -m examples.stop_drill
"""

from __future__ import annotations

import asyncio

from agents import set_tracing_disabled

from chapter8.commit import Refused
from chapter8.harness import Harness
from chapter8.phases import Parked, read_phase, request_write, resume_write
from chapter8.records import Forbidden
from chapter8.stop import emergency_stop
from examples import scripted
from examples.reconcile import run as reconcile
from examples.scripted import CLINICIAN

AGENTS = ["reconciliation-reader", "reconciliation-writer"]


async def run() -> None:
    harness: Harness = await reconcile(live=False, show=False)
    read_session = harness.tokens.launch("read", CLINICIAN, "pt-1002")
    outcome = await read_phase(
        harness.reader(scripted.reader_resists()), read_session, harness.store
    )
    assert outcome.proposal is not None
    writer = harness.writer(
        scripted.writer_clean(outcome.proposal, "Nothing written.")
    )
    write_session = harness.tokens.launch("write", CLINICIAN, "pt-1002")
    parked = await request_write(
        writer, write_session, outcome.proposal, harness.store
    )
    assert isinstance(parked, Parked)
    harness.approve(parked, CLINICIAN)
    print("before the stop     1 write committed, 1 signed write waiting to run")

    report = emergency_stop(harness, AGENTS, "security-on-call", "drill")
    print(
        f"stop pressed        by security-on-call, {len(report.stopped)} agents"
    )
    print(f"tokens revoked      {report.tokens_revoked}")
    print(f"approvals voided    {report.approvals_voided}")

    digest = parked.asks[0].digest
    problem = harness.book.problem(
        digest, CLINICIAN, "clinician", harness.clock()
    )
    await resume_write(
        writer, parked, write_session, harness.book, harness.clock()
    )
    print(f"waiting write       rejected on resume: {problem}")
    fresh = harness.tokens.launch("read", CLINICIAN, "pt-1002")
    outcome = await read_phase(
        harness.reader(scripted.reader_resists()), fresh, harness.store
    )
    print(f"new read run        {outcome.status}: {outcome.problems[0]}")
    try:
        harness.store.read(read_session, "MedicationRequest")
    except Forbidden as error:
        print(f"old token, direct   refused by the record server: {error}")
    try:
        arguments = scripted.write_arguments(parked.proposal)
        late = harness.tokens.launch("write", CLINICIAN, "pt-1002")
        harness.committer.commit(late, "write_reconciliation", arguments)
    except Refused as error:
        print(f"direct commit       refused by policy: {error}")
    for reference in report.left_behind:
        print(f"left behind         {reference} was written before the stop")
    print(
        f"record pt-1002      still version {harness.store.version('pt-1002')}"
    )


def main() -> None:
    set_tracing_disabled(True)
    asyncio.run(run())


if __name__ == "__main__":
    main()
