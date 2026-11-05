# Chapter 3: Giving Agents Hands

Companion code for Chapter 3 of *Agentic AI Engineering* (Packt). It builds the
tool layer of an enterprise agent with the OpenAI Agents SDK and the Model
Context Protocol: intent-shaped tools, values carried in the run context rather
than the schema, an atomic idempotent write behind a unique constraint, preview
and execute with a content hash, an approval gate with interrupt and resume,
a small MCP server over Streamable HTTP, and a financial services audit-prep
agent that puts all of it together.

Most of this chapter runs without an API key. The drills, the audit-prep agent,
and every example except the live question in `examples.mcp_connect` drive the
real SDK runner through its scripted test model, because the point of a safety
pattern is to watch it work in a situation you would rather not reproduce with
real money.

## Tested versions

| Package | Version |
| --- | --- |
| Python | 3.11 or later (tested on 3.13) |
| openai-agents | 0.24.0 |
| mcp | 2.3.0 |
| sqlmodel | 0.0.48 |
| pydantic | 2.x |

The pins in `requirements.txt` are the versions every snippet in the chapter
was run against. The MCP specification was revised on July 28, 2026 and the
`mcp` package moved to a redesigned version 2 API with it, so when something in
the chapter does not match what you see, check the pins before anything else.
Inside `mcp` 2.x the server class that used to be called `FastMCP` is
`MCPServer`; the separate `fastmcp` project is not what this chapter uses.

## Setup

```bash
cd Chapter03
python -m venv .venv
source .venv/bin/activate          # macOS and Linux
.venv\Scripts\activate             # Windows PowerShell or cmd
pip install -r requirements.txt
```

Confirm the environment without spending anything:

```bash
python -m examples.intent_tools
pytest
```

Set `OPENAI_API_KEY` only if you want `examples.mcp_connect` to ask the real
model a question at the end. Everything else is offline.

## Running the chapter examples

Each section has a runnable script under `examples/`:

| Chapter section | Command |
| --- | --- |
| Prefer more narrower tools to fewer broader ones | `python -m examples.intent_tools` |
| Idempotency keys, made concrete | `python -m examples.run_context` |
| Preview and execute | `python -m examples.preview_execute` |
| Approval gates, cross-process resume | `python -m examples.resume_from_string` |
| Plugging in with MCP | `python -m examples.mcp_connect` (server running, see below) |

## Running the MCP server

The finance evidence server exposes one read-only tool and one resource over
Streamable HTTP on `http://127.0.0.1:8765/mcp`. Start it in its own terminal
and leave it there:

```bash
python mcp_servers/finance_evidence_server.py
```

Then, in another terminal, `python -m examples.mcp_connect` connects, runs the
agent inside the `async with` block, lists the tool the model was offered,
reads the `schema://accounts` resource, and shows what a run started after the
block has closed looks like. Stop the server before running the third drill.

## Running the failure drills

```bash
python -m drills.retry_after_timeout      # lost response, retry with the same key, one refund
python -m drills.reject_approval          # the reviewer says no, the tool never runs
python -m drills.unavailable_mcp_server   # nothing on port 8765, loud failure before any model call
```

The drills print exactly the console blocks that appear in the chapter. They
use fixed refund identifiers and fixed amounts so that the output is the same
on every machine.

## Running the audit-prep agent

```bash
python -m audit_prep.main
```

The three MCP servers behind the agent run in process through a small adapter
(`audit_prep/inprocess.py`) that implements the SDK's `MCPServer` interface by
calling the `mcp` server applications directly. The tool definitions, the
argument validation, and the result shapes are the real ones; only the wire is
missing. The evidence store marks `publish_evidence_bundle` for approval with
`require_approval`, the same keyword `MCPServerStreamableHttp` takes, and the
run stops there with one interruption. A scripted reviewer approves, the run
resumes, and every tool call is in the journal with the principal, the argument
hash, and the policy version.

## Running the tests

```bash
pytest
```

The tests cover the atomic deduplication under real threads, the approval
policy threshold, the rejection path, the serialized state round trip with a
context override, the schema exclusion of context parameters, the in-process
evidence server, and the two MCP lifecycle failures. They run in about a second
and cost nothing.

## Regenerating the console outputs

```bash
python scripts/capture_outputs.py
```

This runs every offline example and drill, starts the finance evidence server
for the MCP example, stops it for the unavailable-server drill, and writes one
text file per command into `outputs/`.

## Troubleshooting

`ModuleNotFoundError: No module named 'agents'`: the virtual environment is not
activated, or `pip` installed into a different interpreter.

`ModuleNotFoundError: No module named 'mcp.server.mcpserver'`: your `mcp` is a
1.x release. Run `pip install -r requirements.txt` to get 2.3.0.

`Failed to connect to MCP server 'finance-evidence'`: the server is not
running, or it is listening on a different port. Start it with
`python mcp_servers/finance_evidence_server.py` and check that the URL ends in
`/mcp`.

`Server not initialized`: the run started after the `async with` block closed.
The runner lists tools when the run starts, so the run has to live inside the
block.

Every call to a gated tool interrupts, even small ones: the gated tool's
parameters are not all plain JSON values. The pinned SDK consults a
`needs_approval` callable only when it can validate the arguments without
running application code, and a nested Pydantic model counts as application
code. Keep the fields flat, as `execute_refund` does.

## Project map

```
Chapter03/
  ch3/
    deps.py                       RunDeps and the idempotency key derivation
    erp_tools.py                  three intent-shaped ERP tools and a fake ERP
    errors.py                     the error shape for three audiences
    payments.py                   sqlite refund store, create_refund_atomic
    refund_tools.py               issue_refund, execute_refund, the approval policy
    previews.py                   preview and execute with a content hash
    approvals.py                  the approval loop and a scripted reviewer
    journal.py                    ToolCallJournal and a small writer
  examples/                       one runnable script per chapter section
  mcp_servers/
    finance_evidence_server.py    the chapter's MCP server, Streamable HTTP
  drills/                         the three failure drills
  audit_prep/
    models.py                     EvidenceRequest, EvidenceBundleStatus, run context
    fakes.py                      in-memory data, policy, and evidence store
    servers.py                    the three mcp server applications
    inprocess.py                  SDK MCPServer adapter for in-process apps
    agent.py                      the agent factory and the output guardrail
    main.py                       orchestration, approval, journal
  tests/                          pytest, offline
  scripts/capture_outputs.py      saves console output for every command
  outputs/                        the console blocks used in the chapter
```
