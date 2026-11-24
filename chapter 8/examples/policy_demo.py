"""The write policy on nine attempts. Only the first is allowed.

python -m examples.policy_demo
"""

from __future__ import annotations

import asyncio
import copy
import threading

from agents import set_tracing_disabled

from chapter8.approvals import action_hash
from chapter8.harness import Harness
from chapter8.phases import read_phase
from examples import scripted
from examples.scripted import CLINICIAN

TOOL = "write_reconciliation"


async def prepared() -> tuple[Harness, dict]:
    harness = Harness.build()
    session = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    outcome = await read_phase(
        harness.reader(scripted.reader_clean()), session, harness.store
    )
    assert outcome.proposal is not None
    return harness, scripted.write_arguments(outcome.proposal)


def sign(harness: Harness, arguments: dict, approver: str = CLINICIAN) -> None:
    digest = action_hash(TOOL, arguments, "pt-1001")
    harness.book.grant(digest, approver, "clinician", harness.clock())


def show(
    label: str, harness: Harness, arguments: dict, tool: str = TOOL
) -> None:
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    version = harness.store.version("pt-1001")
    decision = harness.policy.decide(session, tool, arguments, version)
    verdict = "allow" if decision.allow else "deny"
    print(f"{label:<30}{verdict:<7}{decision.rule}")


async def run() -> None:
    harness, arguments = await prepared()
    sign(harness, arguments)
    show("signed, unchanged", harness, arguments)

    harness, arguments = await prepared()
    show("never signed", harness, arguments)

    harness, arguments = await prepared()
    sign(harness, arguments)
    edited = copy.deepcopy(arguments)
    edited["changes"][0]["target"] = "MedicationRequest/mr-101"
    show("target edited after signing", harness, edited)

    harness, arguments = await prepared()
    sign(harness, arguments)
    harness.clock.advance(hours=25)
    show("signed 25 hours ago", harness, arguments)

    harness, arguments = await prepared()
    sign(harness, arguments, approver="Practitioner/dr-other")
    show("signed by another clinician", harness, arguments)

    harness, arguments = await prepared()
    sign(harness, arguments)
    harness.store._patients["pt-1001"].version += 1
    show("record changed while waiting", harness, arguments)

    harness, arguments = await prepared()
    sign(harness, arguments)
    for _ in range(5):
        harness.events.append("write_authorized", "reconciliation-writer", TOOL)
    show("sixth write this hour", harness, arguments)

    harness, arguments = await prepared()
    show("tool nobody registered", harness, arguments, tool="export_records")

    harness, arguments = await prepared()
    sign(harness, arguments)
    session = harness.tokens.launch("write", CLINICIAN, "pt-1001")
    harness.policy.limits.writes_per_hour = 1
    allowed = []

    def race() -> None:
        decision = harness.policy.authorize(session, TOOL, arguments, 7)
        allowed.append(decision.allow)

    threads = [threading.Thread(target=race) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    passed = sum(allowed)
    print(
        f"{'20 writers race for 1 slot':<30}{passed} allowed, {20 - passed} denied"
    )


def main() -> None:
    set_tracing_disabled(True)
    asyncio.run(run())


if __name__ == "__main__":
    main()
