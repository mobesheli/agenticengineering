"""Code-led control, run control, recovery, and reflection."""

import asyncio
from decimal import Decimal

import pytest
from agents import function_tool
from agents.testing import ScriptedModel
from openai.types.responses import ResponseOutputMessage, ResponseOutputRefusal

from chapter5 import invoices, recovery, reflection, run_control
from chapter5.recovery import Checkpoints, Step, run_pipeline
from chapter5.run_control import RetryLedger, run_investigation
from examples.scripted import INVESTIGATION_TURNS, calls, says, scripted


def invoice(amount: str) -> dict:
    return {"vendor": "Kessler Werkzeug GmbH", "amount": amount, "currency": "EUR"}


@pytest.mark.parametrize(
    "amount, queue",
    [("9999.99", "ledger"), ("10000", "ledger"), ("10000.01", "review")],
)
async def test_the_review_threshold_lives_in_code(monkeypatch, amount, queue):
    monkeypatch.setattr(
        invoices, "extractor", scripted(invoices.extractor, says(invoice(amount)))
    )
    books = invoices.Books()

    await invoices.process_invoice("Invoice text", books)

    assert len(books.ledger) == (queue == "ledger")
    assert len(books.review_queue) == (queue == "review")
    stored = (books.ledger or books.review_queue)[0]
    assert isinstance(stored.amount, Decimal) and stored.amount == Decimal(amount)


async def test_a_run_that_concludes_returns_the_assessment(monkeypatch):
    agent = scripted(run_control.investigator, *INVESTIGATION_TURNS)
    monkeypatch.setattr(run_control, "investigator", agent)

    result = await run_investigation("alert-0002", "summary", RetryLedger())

    assert result.status == "concluded"
    assert result.assessment.recommendation == "escalate"


async def test_running_out_of_turns_escalates_and_does_not_retry(monkeypatch):
    looping = [
        calls("get_transactions", {"customer_id": "cust-9411"}, f"c{i}")
        for i in range(5)
    ]
    monkeypatch.setattr(
        run_control, "investigator", scripted(run_control.investigator, *looping)
    )
    monkeypatch.setattr(run_control, "TURN_CAP", 2)

    result = await run_investigation("alert-0002", "summary", RetryLedger())

    assert result.status == "escalated_to_human"


async def test_running_out_of_time_escalates(monkeypatch):
    @function_tool
    async def slow_lookup() -> str:
        """A lookup that hangs."""
        await asyncio.sleep(5)
        return "late"

    agent = run_control.investigator.clone(
        tools=[slow_lookup], model=ScriptedModel([calls("slow_lookup", {})])
    )
    monkeypatch.setattr(run_control, "investigator", agent)
    monkeypatch.setattr(run_control, "TIME_CAP_SECONDS", 0.05)

    result = await run_investigation("alert-0002", "summary", RetryLedger())

    assert result.status == "escalated_to_human"


async def test_a_refusal_goes_to_a_person_not_to_a_retry(monkeypatch):
    refusal = ResponseOutputMessage(
        id="m1",
        role="assistant",
        status="completed",
        type="message",
        content=[
            ResponseOutputRefusal(type="refusal", refusal="I cannot help with that.")
        ],
    )
    monkeypatch.setattr(
        run_control, "investigator", scripted(run_control.investigator, [refusal])
    )
    retries = RetryLedger()

    result = await run_investigation("alert-0002", "summary", retries)

    assert result.status == "escalated_to_human"
    assert await retries.record_attempt("alert-0002") == 1


async def test_malformed_output_is_retried_once_and_the_count_is_stored(
    monkeypatch, tmp_path
):
    path = str(tmp_path / "retries.db")

    async def attempt() -> str:
        agent = scripted(run_control.investigator, says("not json at all"))
        monkeypatch.setattr(run_control, "investigator", agent)
        return (
            await run_investigation("alert-0002", "summary", RetryLedger(path))
        ).status

    assert await attempt() == "retry_queued"
    assert await attempt() == "escalated_to_human"


async def test_a_resumed_pipeline_skips_completed_steps_and_reuses_the_key(tmp_path):
    store = Checkpoints(str(tmp_path / "checkpoints.db"))
    holds: dict[str, str] = {}
    ran: list[str] = []

    def step(name: str, fail_once: bool = False) -> Step:
        async def run(done: dict, key: str) -> str:
            ran.append(name)
            if name == "place_hold":
                holds.setdefault(key, "hold placed")
            if fail_once and ran.count(name) == 1:
                raise ConnectionError("worker restarted")
            return f"{name} done"

        return Step(name, run)

    steps = [step("gather"), step("place_hold", fail_once=True), step("summarize")]

    with pytest.raises(ConnectionError):
        await run_pipeline("run-7", steps, store)
    done = await run_pipeline(
        "run-7", steps, Checkpoints(str(tmp_path / "checkpoints.db"))
    )

    assert ran == ["gather", "place_hold", "place_hold", "summarize"]
    assert holds == {"run-7:place_hold": "hold placed"}
    assert list(done) == ["gather", "place_hold", "summarize"]
    assert recovery.Step is Step


async def test_a_draft_is_revised_until_the_reviewer_accepts(monkeypatch):
    monkeypatch.setattr(
        reflection,
        "narrative_writer",
        scripted(
            reflection.narrative_writer, says("Draft one."), says("Draft two [txn-1].")
        ),
    )
    monkeypatch.setattr(
        reflection,
        "narrative_reviewer",
        scripted(
            reflection.narrative_reviewer,
            says({"acceptable": False, "problems": ["No record cited."]}),
            says({"acceptable": True, "problems": []}),
        ),
    )

    narrative = await reflection.draft_with_review("[txn-1] 9,400 GBP cash deposit")

    assert narrative.passed_review and narrative.revisions == 1
    assert narrative.text == "Draft two [txn-1]."


async def test_the_reflection_loop_stops_and_says_it_did_not_pass(monkeypatch):
    drafts = [says(f"Draft {n}.") for n in range(3)]
    rejections = [
        says({"acceptable": False, "problems": ["Still wrong."]}) for _ in range(3)
    ]
    monkeypatch.setattr(
        reflection, "narrative_writer", scripted(reflection.narrative_writer, *drafts)
    )
    monkeypatch.setattr(
        reflection,
        "narrative_reviewer",
        scripted(reflection.narrative_reviewer, *rejections),
    )

    narrative = await reflection.draft_with_review("records", max_revisions=2)

    assert not narrative.passed_review and narrative.revisions == 2
    assert narrative.text == "Draft 2."
