# Chapter 2: From Zero to Agent

Companion code for Chapter 2 of *Agentic AI Engineering* (Packt). It builds a
claims processing pipeline for a property and casualty insurer with the OpenAI
Agents SDK: three agents with structured output, async function tools with
timeouts, an input guardrail, an output guardrail, deterministic escalation
rules, and tracing.

Every example here calls the real API. There is no offline or mock mode. The
only command that does not need a key is `describe`.

## Tested versions

| Package | Version |
| --- | --- |
| Python | 3.10 or later (tested on 3.13) |
| openai-agents | 0.24.0 |
| pydantic | 2.x |

The pin in `requirements.txt` is the version every snippet in the chapter was
run against. Newer releases of the SDK usually work, but when something in the
chapter does not match what you see, check the pin first.

## Setup

```bash
cd Chapter02
python -m venv .venv
source .venv/bin/activate          # macOS and Linux
.venv\Scripts\activate             # Windows PowerShell or cmd
pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key-here"      # macOS and Linux
$env:OPENAI_API_KEY = "your-api-key-here"      # Windows PowerShell
```

Confirm the environment without spending anything:

```bash
python main.py describe
```

## Running the chapter examples

Each section of the chapter has a runnable script under `examples/`:

| Chapter section | Command |
| --- | --- |
| Creating an agent and running it | `python -m examples.first_agent` and `python -m examples.first_agent_async` |
| Structuring agent output with Pydantic | `python -m examples.structured_output` |
| Building function tools | `python -m examples.tool_using_agent` |
| Streaming agent responses | `python -m examples.streaming` |
| Guardrails and constraints | `python -m examples.guardrails` |
| Implementing handoffs | `python -m examples.handoffs` |
| Enabling tracing | `python -m examples.tracing` |

## Running the claims pipeline

```bash
python main.py list-claims
python main.py run --claim CLM-4821     # complete claim, approved
python main.py run --claim CLM-4822     # missing contractor estimate, stops after intake
python main.py run --claim CLM-4823     # large loss, escalated to a human
python main.py run --off-topic          # input guardrail rejects the request
```

Every run prints a `trace_id`. Open it in the OpenAI Traces dashboard to see the
agent spans, tool calls, and guardrail evaluations.

## Running the tests

```bash
pytest
```

The tests exercise the real SDK runner with the SDK's own `ScriptedModel`
test double, so they run in about a second and cost nothing. Set
`OPENAI_API_KEY` and the live tests in `tests/test_live.py` run too.

## Cost

A full pipeline run makes between three and seven model calls: the topic
classifier, the intake agent (one tool call), the reviewer (two tool calls), and,
for escalated claims, the coordinator. The registry in `claims_pipeline/settings.py` pins a
small model for classification and intake and a mid-tier model for review. At
the list prices current when this chapter was written, one run costs a cent or
two; running every example and all three sample claims a dozen times stays
under a dollar. Long policies, extra retries, and a larger model change that
arithmetic, so check the prices for whatever the registry points at.

## Troubleshooting

`ModuleNotFoundError: No module named 'agents'`: the virtual environment is not
activated, or `pip` installed into a different interpreter. Run
`python -c "import sys; print(sys.executable)"` and compare it with
`which python` (or `where python` on Windows).

`OPENAI_API_KEY is not set`: export the variable in the same shell session you
run the commands from. A key set in one terminal tab is not visible in another.

`AuthenticationError` or `RateLimitError`: the key is wrong, or the project has
no credit. Check the billing page for the project the key belongs to.

A parameter from the chapter is rejected with a `TypeError`: your installed
SDK is older or newer than the pin. Run `pip install -r requirements.txt` to
match it.

## Project map

```
Chapter02/
  main.py                         command-line entry point
  claims_pipeline/
    settings.py                   model registry and business thresholds
    models.py                     Pydantic models for every stage
    data.py                       in-memory policies, claims, and history
    tools.py                      async function tools with timeouts
    guardrails.py                 input and output guardrails
    rules.py                      deterministic escalation rules
    agents.py                     agent definitions and the handoff graph
    pipeline.py                   orchestration, failure paths, tracing
  examples/                       one runnable script per chapter section
  tests/                          rules, wiring, scripted pipeline, live checks
  scripts/capture_outputs.py      saves console output for every example
  Chapter_2_Learning_Walkthrough.ipynb
```
