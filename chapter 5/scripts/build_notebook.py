"""Build Chapter_5_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. Every cell that needs a model
drives the SDK runner through its scripted test model, so the whole notebook runs
without an API key.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_5_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 5: Who Runs the Show

This notebook mirrors the chapter. Run the cells in order, from the `Chapter05`
folder. Nothing here needs an API key. The SDK runner, the tools, the handoffs,
the approval flow, and the run state are all real. Only the model's replies are
scripted.

Pinned version: openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from agents import RunConfig, Runner
from agents.testing import ScriptedModel

from examples.scripted import (INVESTIGATION_TURNS, TRIAGE_REPLIES, calls, says,
                               scripted)

print("openai-agents", version("openai-agents"))


def one_model(*turns):
    return RunConfig(model=ScriptedModel(list(turns)), tracing_disabled=True)
"""
    ),
    md(
        """
## Choosing who controls the flow: Your code or the model

The invoice workflow sits at the code-led end of the dial. The model extracts
three fields. A Python comparison decides whether the invoice needs review.
"""
    ),
    code(
        """
from examples import invoice

books = await invoice.main(scripted_run=True)
print("ledger:", [str(i.amount) for i in books.ledger])
print("review queue:", [str(i.amount) for i in books.review_queue])
print("amount type:", type(books.ledger[0].amount).__name__)
"""
    ),
    md(
        """
## Controlling an agent run

### Understanding the outcomes of an agent run

`run_investigation` returns a typed result for every ending. First, a run that
concludes. Then the same agent stuck in a loop, with the turn cap lowered to two
so the cap is reached quickly.
"""
    ),
    code(
        """
from chapter5 import run_control
from chapter5.run_control import RetryLedger, run_investigation

original = run_control.investigator
run_control.investigator = scripted(original, *INVESTIGATION_TURNS)
result = await run_investigation("alert-0002", "summary", RetryLedger())
print(result.status, "|", result.assessment.recommendation, result.assessment.evidence)

looping = [calls("get_transactions", {"customer_id": "cust-9411"}, f"c{i}") for i in range(5)]
run_control.investigator = scripted(original, *looping)
run_control.TURN_CAP = 2
result = await run_investigation("alert-0002", "summary", RetryLedger())
print(result.status, "|", result.reason)
run_control.TURN_CAP = 12
"""
    ),
    md(
        """
Malformed output is the one failure worth retrying, once. The count of attempts
is kept in a database, so a restarted worker cannot forget it.
"""
    ),
    code(
        """
retries = RetryLedger()
for attempt in (1, 2):
    run_control.investigator = scripted(original, says("this is not the expected JSON"))
    result = await run_investigation("alert-0002", "summary", retries)
    print(f"attempt {attempt}: {result.status} | {result.reason}")
run_control.investigator = original
"""
    ),
    md(
        """
### Calculating reliability across multiple steps

The table from the chapter, computed. The figures assume that failures are
independent, which real pipelines rarely grant you.
"""
    ),
    code(
        """
print("per step    5 steps  10 steps  20 steps")
for rate in (0.99, 0.97, 0.90):
    row = "  ".join(f"{rate ** steps:8.1%}" for steps in (5, 10, 20))
    print(f"{rate:8.0%}  {row}")
"""
    ),
    md(
        """
### Resuming a workflow after a crash

The second step places a hold and then crashes before its checkpoint is saved.
A second worker resumes the same run. Watch the number of holds on file.
"""
    ),
    code(
        """
from examples import crash_and_resume

await crash_and_resume.main()
"""
    ),
    md(
        """
### Letting an agent check its own work

A writer and a reviewer with different instructions, and a fixed number of
rounds. The reviewer rejects the first draft and accepts the second.
"""
    ),
    code(
        """
from chapter5 import reflection

writer, reviewer = reflection.narrative_writer, reflection.narrative_reviewer
reflection.narrative_writer = scripted(
    writer, says("Two deposits were made."), says("Two deposits were made [txn-7310, txn-7311].")
)
reflection.narrative_reviewer = scripted(
    reviewer,
    says({"acceptable": False, "problems": ["No record is cited."]}),
    says({"acceptable": True, "problems": []}),
)
narrative = await reflection.draft_with_review("[txn-7310] 9,400 GBP cash\\n[txn-7311] 9,300 GBP cash")
print(narrative.passed_review, narrative.revisions, "|", narrative.text)
reflection.narrative_writer, reflection.narrative_reviewer = writer, reviewer
"""
    ),
    md(
        """
## Routing incoming requests

### Choosing between agents as tools and handoffs

One intake agent, three options. A dispute is handed off with a typed reason. A
fee question is answered by a function, and the intake agent keeps the
conversation.
"""
    ),
    code(
        """
from chapter5 import routing

routing.TRANSFERS.clear()
transfer = calls(
    "transfer_to_dispute_specialist",
    {"reason": "Charged twice by the hotel.", "transaction_reference": "txn-8841"},
)
run = await Runner.run(
    routing.intake_agent,
    "The hotel charged me twice.",
    run_config=one_model(transfer, says("I have opened a dispute for txn-8841.")),
)
print("conversation now owned by:", run.last_agent.name)
print("recorded reason:", routing.TRANSFERS[0])

run = await Runner.run(
    routing.intake_agent,
    "What would 650 payments cost on premium?",
    run_config=one_model(
        calls("estimate_fees", {"tier": "premium", "payments": 650}),
        says("150 billable payments, 15.00 in fees."),
    ),
)
tool_output = next(i.output for i in run.new_items if i.type == "tool_call_output_item")
print("conversation still owned by:", run.last_agent.name)
print("the function returned:", tool_output)
"""
    ),
    md(
        """
### Building a router with an escalation option

A confident decision reaches a specialist. A decision below the threshold, or
one classified as `other`, goes to a person.
"""
    ),
    code(
        """
from chapter5 import router

real_router, real_specialists = router.request_router, dict(router.SPECIALISTS)
decisions = [
    {"category": "dispute", "confidence": 0.93, "reason": "Double charge."},
    {"category": "balance_inquiry", "confidence": 0.62, "reason": "Unclear wording."},
    {"category": "other", "confidence": 0.99, "reason": "Not a banking request."},
]
for decision in decisions:
    router.request_router = scripted(real_router, says(decision))
    for name, agent in real_specialists.items():
        router.SPECIALISTS[name] = scripted(agent, says(f"{name} specialist replied"))
    outcome = await router.dispatch("A customer request.")
    print(f"{decision['category']:16} {decision['confidence']:.2f} -> {outcome.handled_by}")
router.request_router = real_router
router.SPECIALISTS.update(real_specialists)
"""
    ),
    md(
        """
### Evaluating routing accuracy

The report from the chapter, on the 24 labeled requests in `data/`. The sample
is far too small for a real evaluation. It is here to show the shape of the trade.
"""
    ),
    code(
        """
from chapter5.router_eval import Scored
from examples.router_report import SAMPLE, report

recorded = [Scored(i["label"], i["predicted"], i["confidence"]) for i in SAMPLE]
print("\\n".join(report(recorded)))
"""
    ),
    md(
        """
## Routing models: The cheapest big decision in your architecture

The registry is the only place a model name appears. The canary split is a hash
of the request identifier, so the same request always gets the same model.
"""
    ),
    code(
        """
from collections import Counter

from chapter5.canary import pick_frontier_model
from chapter5.models import DEEP, MODELS, QUICK

print(MODELS)
print("quick:", QUICK.reasoning.effort, "| deep:", DEEP.reasoning.effort)
split = Counter(pick_frontier_model(f"request-{n}") for n in range(20_000))
print({model: f"{count / 20_000:.1%}" for model, count in split.items()})
print("stable:", pick_frontier_model("request-42") == pick_frontier_model("request-42"))
"""
    ),
    md(
        """
## Plans, fan-out, and supervisors: Paying the coordination tax

### Creating and validating an execution plan

A plan is data, so it can be checked before anything runs. A revision is held to
the record of what has already been done.
"""
    ),
    code(
        """
from chapter5.planning import (ExecutionRecord, Plan, PlanStep, validate_plan,
                               validate_revision, writes_needing_approval)

TOOLS = {"get_transactions", "screen_counterparty", "place_hold"}


def step(step_id, tool, writes=False, description="d"):
    return PlanStep(step_id=step_id, description=description, tool=tool, writes=writes, success_check="c")


plan = Plan(goal="Investigate alert-0002", steps=[
    step("s1", "get_transactions"), step("s2", "wire_funds", True), step("s3", "place_hold", True)])
print(validate_plan(plan, TOOLS, max_steps=2))

record = ExecutionRecord(completed={"s1": "42 transactions read"}, replans=0)
revised = Plan(goal="Investigate alert-0002", steps=[
    step("s1", "get_transactions"), step("s4", "screen_counterparty")])
print(validate_revision(revised, record, TOOLS, max_steps=6))

approved = Plan(goal="g", steps=[step("s3", "place_hold", True, "Hold account 1")])
wider = Plan(goal="g", steps=[step("s3", "place_hold", True, "Hold account 1"),
                              step("s5", "place_hold", True, "Hold account 2")])
print("needs a fresh approval:", [s.step_id for s in writes_needing_approval(approved, wider)])
"""
    ),
    md(
        """
### Running independent tasks in parallel

Three specialists run at once and their views are merged in code. In the second
run, one specialist fails. It is named in the result, and the combined risk is
high.
"""
    ),
    code(
        """
from chapter5 import fanout

real = list(fanout.SPECIALISTS)


def view(source, risk, evidence):
    return {"source": source, "risk": risk, "evidence": evidence, "summary": "s"}


replies = [view("sanctions", "low", ["txn-7312"]), view("patterns", "high", ["txn-7310", "txn-7311"]),
           view("network", "low", [])]
fanout.SPECIALISTS = [scripted(a, says(r)) for a, r in zip(real, replies)]
print(await fanout.gather_specialist_views("alert-0002"))

fanout.SPECIALISTS = [scripted(real[0], says(replies[0])), scripted(real[1], says("not json")),
                      scripted(real[2], says(replies[2]))]
print(await fanout.gather_specialist_views("alert-0002"))
fanout.SPECIALISTS = real
"""
    ),
    md(
        """
## Integrating human review into workflows

### Pausing and resuming work for human approval

A payment above the limit pauses the run. The paused run is stored in a database
file and resumed through a second store object, standing in for a second worker.
"""
    ),
    code(
        """
from examples import approval_roundtrip

await approval_roundtrip.main(scripted_run=True)
"""
    ),
    md(
        """
A rejection reaches the model as the tool's result, and nothing is released.
A request that nobody answers is rejected and held. Silence is not consent.
"""
    ),
    code(
        """
from chapter5 import approvals
from chapter5.approvals import ApprovalStore, advance_payment, hold_overdue, resume_payment

real_agent = approvals.payments_agent
case = approval_roundtrip.CASE
call = calls("release_payment", {"payment_id": "pay-118", "amount_cents": 750_000})

approvals.RELEASED.clear()
store = ApprovalStore()
approvals.payments_agent = scripted(real_agent, call, says("The payment was not released."))
await advance_payment(case, store)
done = await resume_payment(case.case_id, False, "Beneficiary changed last week.", store)
print("rejected:", done.state, "| released:", approvals.RELEASED)

store = ApprovalStore()
approvals.payments_agent = scripted(real_agent, call, says("The payment stays on hold."))
await advance_payment(case, store)
held = await hold_overdue(store, datetime.now(UTC) + timedelta(hours=5))
print("unanswered:", [h.state for h in held], "| released:", approvals.RELEASED)
approvals.payments_agent = real_agent
"""
    ),
    md(
        """
## Putting it together: The alert triage pyramid

Four sample alerts through the three layers. Each one takes a different route.
The third is the one to study: the model was 97 percent confident, and policy
sent it to a person anyway.
"""
    ),
    code(
        """
from examples import triage_day

desk = await triage_day.main(scripted_run=True)
"""
    ),
    md(
        """
### Estimating the costs of triage and investigation

The arithmetic from the chapter. Change the prices or the token counts in
`chapter5/costs.py` and run it again.
"""
    ),
    code(
        """
from chapter5.costs import triage_report

print("\\n".join(triage_report(alerts_per_day=10_000)))
"""
    ),
    md(
        """
## Where to go next

Run `python -m pytest -q` to see the same behavior asserted in tests. Then set
`OPENAI_API_KEY` and run the scripts under `examples/` without `--scripted` to
watch a real model make the same decisions.
"""
    ),
]


def main() -> None:
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    NotebookClient(
        notebook, timeout=180, resources={"metadata": {"path": str(ROOT)}}
    ).execute()
    nbf.write(notebook, OUT)
    print(f"wrote {OUT.name} with {len(cells)} cells")


if __name__ == "__main__":
    main()
