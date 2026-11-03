"""Build Chapter_2_Learning_Walkthrough.ipynb from the chapter's runnable examples.

    python scripts/build_notebook.py

The notebook calls the real API. Set OPENAI_API_KEY before running it.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_2_Learning_Walkthrough.ipynb"

SETUP = '''import os, sys
sys.path.insert(0, os.path.abspath("."))
assert os.getenv("OPENAI_API_KEY"), "Set OPENAI_API_KEY before running this notebook."
import agents
print("openai-agents", agents.__version__)'''

CELLS: list[tuple[str, str | None]] = [
    (
        "# Chapter 2: From Zero to Agent\n\n"
        "This notebook follows the chapter section by section. Every cell that calls `Runner` makes a "
        "real API call, so run it from the `Chapter02` directory with `OPENAI_API_KEY` exported and the "
        "pinned SDK installed (`pip install -r requirements.txt`).",
        SETUP,
    ),
    (
        "## Wiring the reasoning core\n\nThe simplest agent the SDK accepts: a name, a model from the "
        "registry, and instructions. Nothing runs until the `Runner` is involved. A notebook already has an event loop running, so every cell here uses `await Runner.run` rather than `Runner.run_sync`, which the SDK documents as unusable inside a running loop.",
        '''from agents import Agent, Runner
from claims_pipeline.settings import MODELS

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=(
        "You are a senior insurance claims reviewer. "
        "Analyze submitted claims for completeness, "
        "flag missing documentation, and assess whether "
        "the claim falls within standard policy coverage. "
        "Always cite the specific policy section that "
        "applies to your determination."
    ),
)

CLAIM_TEXT = (
    "Claim #4821: Water damage to basement. "
    "Policy: HO-3. Date of loss: 2026-01-15. "
    "Submitted documents: photos, contractor estimate."
)

result = await Runner.run(claims_reviewer, CLAIM_TEXT, max_turns=10)
print(result.final_output)''',
    ),
    (
        "## Structuring agent output\n\nAttach a Pydantic model through `output_type`. The `Literal` "
        "and `Field` constraints reject shapes the pipeline cannot handle, but remember: validation "
        "proves shape, not correctness.",
        '''from claims_pipeline.agents import REVIEW_INSTRUCTIONS
from claims_pipeline.models import ClaimVerdict

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=REVIEW_INSTRUCTIONS,
    output_type=ClaimVerdict,
)

result = await Runner.run(claims_reviewer, CLAIM_TEXT)
verdict = result.final_output
print(type(verdict).__name__)
print(verdict.model_dump_json(indent=2))''',
    ),
    (
        "## Giving your agent hands\n\nThe two function tools from the chapter. Both are `async` "
        "with a timeout, and `get_claim_history` enforces in code the range its docstring only "
        "advises. Watch the tool calls appear in `result.new_items`.",
        '''from claims_pipeline.data import SAMPLE_CLAIMS
from claims_pipeline.tools import get_claim_history, lookup_policy

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=REVIEW_INSTRUCTIONS,
    output_type=ClaimVerdict,
    tools=[lookup_policy, get_claim_history],
)

claim = SAMPLE_CLAIMS["CLM-4821"]
result = await Runner.run(claims_reviewer, claim.as_text())
for item in result.new_items:
    if item.type == "tool_call_item":
        print("tool call:", item.raw_item.name, item.raw_item.arguments)
print(result.final_output.model_dump_json(indent=2))''',
    ),
    (
        "## Streaming agent responses\n\n`Runner.run_streamed` yields events as they happen. In a "
        "notebook, `await` works directly at the top level.",
        '''async def stream_review(claim_text: str) -> None:
    streamed = Runner.run_streamed(claims_reviewer, claim_text)
    async for event in streamed.stream_events():
        if event.type == "raw_response_event" and hasattr(event.data, "delta"):
            print(event.data.delta, end="", flush=True)
    print()

await stream_review(CLAIM_TEXT)''',
    ),
    (
        "## Drawing the boundaries\n\nThe pipeline's agents carry their guardrails already attached. "
        "An off-topic request trips the blocking input guardrail before the intake model is called.",
        '''from agents.exceptions import InputGuardrailTripwireTriggered
from claims_pipeline.agents import intake_agent
from claims_pipeline.data import OFF_TOPIC_REQUEST

print("input guardrails:", [g.name for g in intake_agent.input_guardrails])
try:
    await Runner.run(intake_agent, OFF_TOPIC_REQUEST)
    print("not rejected")
except InputGuardrailTripwireTriggered as exc:
    print("rejected:", exc.guardrail_result.output.output_info)''',
    ),
    (
        "## Routing work between agents\n\nThe triage agent hands off to one of two specialists, with "
        "tool history filtered on the way. `result.last_agent` shows who answered.",
        '''from agents import RunConfig
from agents.extensions import handoff_filters
from claims_pipeline.agents import triage_agent

config = RunConfig(handoff_input_filter=handoff_filters.remove_all_tools)
result = await Runner.run(
    triage_agent,
    "Does my HO-2024822 policy cover wind damage to a detached garage?",
    run_config=config,
)
print("answered by:", result.last_agent.name)
print(result.final_output)''',
    ),
    (
        "## Watching what your agent does\n\nA valid trace ID from `gen_trace_id()`, the claim "
        "reference in `trace_metadata`, and no claim text in the trace store. Open the printed "
        "trace ID in the OpenAI Traces dashboard.",
        '''from agents.tracing import gen_trace_id

trace_id = gen_trace_id()
config = RunConfig(
    workflow_name="claims_processing",
    trace_id=trace_id,
    group_id="batch-daily-claims",
    trace_metadata={"claim_ref": claim.claim_id},
    trace_include_sensitive_data=False,
)
result = await Runner.run(claims_reviewer, claim.as_text(), run_config=config)
print("trace:", trace_id)
print(result.final_output.decision, result.final_output.cited_sections)''',
    ),
    (
        "## Putting it all together\n\nThe full pipeline: three agents, deterministic routing, "
        "enforced thresholds, and one trace per claim. Each sample claim leaves through a different exit.",
        '''from claims_pipeline.pipeline import process_claim

for claim_id in ("CLM-4821", "CLM-4822", "CLM-4823"):
    outcome = await process_claim(SAMPLE_CLAIMS[claim_id])
    print(outcome.model_dump_json(indent=2, exclude_none=True))
    print("-" * 60)''',
    ),
    (
        "### The failure path\n\nThe same function with a request that is not an insurance claim. "
        "The input guardrail trips and the pipeline returns a structured rejection. The request itself is the only line in this notebook written for the author's benefit rather than yours.",
        '''from claims_pipeline.models import Claim

off_topic = Claim(
    claim_id="REQ-0000",
    policy_number="XX-0000000",
    policyholder_id="PH-00000",
    claim_type="property",
    amount_usd=1.0,
    date_of_loss="2026-01-01",
    submitted_documents=[],
    description="A raw submission that is not a claim.",
    raw_submission=OFF_TOPIC_REQUEST,
)
outcome = await process_claim(off_topic)
print(outcome.model_dump_json(indent=2, exclude_none=True))''',
    ),
    (
        "## Where to go next\n\nRun `pytest` to exercise the pipeline against the SDK's scripted "
        "model double, then open `claims_pipeline/rules.py` and change a threshold. Chapter 3 picks up "
        "from here with tools that pause for human approval and MCP servers.",
        None,
    ),
]


def main() -> None:
    nb = new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    for markdown, code in CELLS:
        nb.cells.append(new_markdown_cell(markdown))
        if code:
            nb.cells.append(new_code_cell(code))
    nbformat.write(nb, OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
