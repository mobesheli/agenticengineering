# Chapter 3 companion code: verification record

Date of the run: 2026-11-05. Working directory: `book-code/chapter3`.
Interpreter: the `venv-oa24` virtual environment, Python 3.13.18.

## Versions

| Package | Version |
| --- | --- |
| openai-agents | 0.24.0 |
| openai | 3.42.1 |
| mcp | 2.3.0 (protocol revision 2026-07-28) |
| sqlmodel | 0.0.48 |
| SQLAlchemy | 2.1.8 |
| pydantic | 2.14.2 |
| pytest | 9.0.2 |
| pytest-asyncio | 1.4.1.post1 |
| uvicorn / starlette | 0.54.0 / 1.10.0 (pulled in by `mcp`) |

`sqlmodel` was the only package installed for this work (`pip install sqlmodel`
into the venv, which brought SQLAlchemy 2.1.8). Nothing else was changed.

## Commands run

All commands from `book-code/chapter3`, with `python` being the venv interpreter.

```bash
python -m pytest -q                              # 31 passed in 0.6s
python -m examples.intent_tools
python -m examples.run_context
python -m examples.preview_execute
python -m examples.resume_from_string
python -m drills.retry_after_timeout
python -m drills.reject_approval
python -m audit_prep.main
python mcp_servers/finance_evidence_server.py    # in the background, port 8765
python -m examples.mcp_connect                   # with the server running
# server stopped
python -m drills.unavailable_mcp_server          # with nothing on port 8765
python scripts/capture_outputs.py                # does all of the above and writes outputs/
python -m pyflakes ch3 examples drills audit_prep mcp_servers tests scripts   # clean
```

`scripts/capture_outputs.py` starts the finance evidence server as a child
process for the MCP example, stops it, and then runs the unavailable-server
drill, so each saved output shows the situation the chapter describes. The
saved files are in `outputs/` with these keys: `drill_retry`, `drill_reject`,
`drill_unavailable`, `mcp_connect`, `intent_tools`, `run_context`,
`preview_execute`, `resume_from_string`, `audit_prep`.

No `OPENAI_API_KEY` was present. Every command above ran without one. The
drills and the offline examples call `set_tracing_disabled(True)`, so the
SDK's "OPENAI_API_KEY is not set, skipping trace export" line does not appear
on stdout or stderr for any drill. The one remaining stderr line in the whole
set is from `examples.resume_from_string`, where the SDK logs
`RunState context was serialized from a Pydantic model. Provide
context_deserializer or context_override to restore the original type.` at the
`state.to_string()` call. It is a logger warning, it is not in the captured
stdout, and it says exactly what the chapter prose now says to do.

## Drill outputs, verbatim

`outputs/drill_retry.txt`

```console
first call : issued   refund_id=rf_7f3a9c amount_cents=21450
network    : response lost, orchestration retries with the same key
second call: replayed refund_id=rf_7f3a9c amount_cents=21450
refunds in store: 1
```

`outputs/drill_reject.txt`

```console
interruption : execute_refund({"customer_id": "cus_8841", "original_charge_id": "ch_3f9a21", "amount_cents": 21450, "reason": "Damaged on arrival"})
reviewer     : rejected, reason: Amount exceeds the self-service limit for this customer tier
tool ran     : no (refunds in store: 0)
final output : I was not able to issue the $214.50 refund. A reviewer declined it because the amount exceeds the self-service limit for this customer tier. I can raise it with the billing team if you would like.
```

`outputs/drill_unavailable.txt`

```console
error  : Failed to connect to MCP server 'finance-evidence'
reason : Could not reach the server. (http://127.0.0.1:8765/mcp)
model calls made: 0
```

`outputs/mcp_connect.txt` (server running)

```console
connected  : finance-evidence
run started: 1 tool(s) listed for the model: get_trial_balance_snapshot
tool result: { "ok": true, "entity": "UK01", "period": "2026-Q3", "materiality_threshold": 1000000, "source_ref": "tb:UK01:...
final      : Six accounts sit above the threshold for UK01 in 2026-Q3.
resource   : schema://accounts
             accounts:
               - code: "1000"
                 name: Cash and cash equivalents
after block: Server not initialized, model calls made: 0
OPENAI_API_KEY is not set; the live question was skipped
```

The other captured outputs (`intent_tools`, `run_context`, `preview_execute`,
`resume_from_string`, `audit_prep`) are in `outputs/` and match Table 3.1.

## How the drills work

- `drills/retry_after_timeout.py` runs the real `Runner.run` with a
  `ScriptedModel` that calls `issue_refund` once. A `LossyChannel` drops the
  delivery of the first run result after the tool has committed, which is the
  gateway-timeout story from the chapter. The orchestration layer retries the
  run with the same `RunDeps`, so the same key reaches the tool and the store
  replays. The "first call" line reads the row the processor side already has;
  the "second call" line reads the typed `RefundResult` from the run items.
- `drills/reject_approval.py` runs the chapter's approval loop verbatim
  (`ch3/approvals.py::run_with_approvals`) with a `ScriptedReviewer` that says
  no. The interruption's tool name and arguments are printed, the store is
  checked to prove the tool did not run, and the scripted model's final message
  is the one the user would see.
- `drills/unavailable_mcp_server.py` enters `MCPServerStreamableHttp` against
  port 8765 with nothing listening, catches the SDK's `UserError`, and prints the
  server name and reason. No agent is built and no model step is consumed.

## Chapter snippet lines that must change

One line cannot work as printed against the pinned versions.

1. `ToolCallJournal`, the `status` column (Part 3, journal block). sqlmodel
   0.0.48 cannot map a bare `Literal[...]` annotation to a column. Defining the
   class raises `TypeError: issubclass() arg 1 must be a class` from
   `sqlmodel/main.py::get_sqlalchemy_type`. The smallest fix tells SQLAlchemy the
   column type while keeping the `Literal` for validation:

   As printed:
   ```python
   from sqlmodel import Field, SQLModel
   ...
       status: Literal["pending", "succeeded", "failed", "replayed"]
   ```
   Corrected:
   ```python
   from sqlmodel import Field, SQLModel, String
   ...
       status: Literal["pending", "succeeded", "failed", "replayed"] = Field(sa_type=String)
   ```
   `sa_type` has existed since sqlmodel 0.0.14, so this is safe for the
   `sqlmodel>=0.0.24` requirement. The companion `ch3/journal.py` uses it.

Everything else in the chapter's code blocks is reproduced line for line in the
companion files, with the following non-semantic differences a reader will
notice:

- Imports are consolidated per file (for example `from typing import Annotated,
  Literal` in `ch3/refund_tools.py`, `from datetime import datetime, timezone`
  in `ch3/journal.py`). No shown import is missing; several are merged.
- The error-shape dictionary is bound to a name, `RATE_LIMITED_EXAMPLE`, in
  `ch3/errors.py`, so the chapter's opening `{` line reads
  `RATE_LIMITED_EXAMPLE: ToolError = {`.
- The approval loop and the `agent = Agent(...)` block sit inside functions
  (`run_with_approvals` and `build_agent`), so they are indented and the loop's
  final `print(result.final_output)` becomes `return result`, with the caller
  printing.
- `RunDeps` lives in `ch3/deps.py` and the refund models and tools in
  `ch3/refund_tools.py`; the chapter shows them in one block.
- `mcp_servers/finance_evidence_server.py` defines a small `FakeLedger` above
  the chapter's lines so that `ledger` exists; the printed lines are unchanged.

## Facts confirmed against the pinned SDK that shaped the code

- A `needs_approval` callable is consulted only when every parameter of the
  tool is a plain JSON value. With a nested Pydantic model parameter the SDK
  routes every call to approval without calling the policy
  (`agents/util/_approvals.py::evaluate_function_tool_approval` together with
  `agents/_function_tool_arguments.py::can_prepare_without_user_code`). The
  flat `execute_refund` in the chapter works: 500 and 10,000 cents flow,
  10,001 and 21,450 cents interrupt (`tests/test_approvals.py`).
- `Annotated[int, Field(gt=0)]` and `Annotated[str, Field(max_length=200)]`
  keep the parameters "plain" for that check and still produce
  `exclusiveMinimum` and `maxLength` in the model-facing schema.
- `RunState.from_string` is a coroutine and must be awaited.
  `context_override=deps` accepts the Pydantic `RunDeps` instance and the
  resumed tool reads `ctx.context.idempotency_key` correctly
  (`examples/resume_from_string.py`, `tests/test_approvals.py`). Without the
  override the context comes back as a dictionary and the tool fails closed
  with the SDK's generic tool error; no refund is written.
- `MCPServerStreamableHttp` raises `UserError("Failed to connect to MCP server
  'finance-evidence': Could not reach the server.")` on enter when nothing is
  listening. A run against a server object that was never entered raises
  `UserError("Server not initialized. ...")` before any model call. The tool
  list is fetched by the runner when the run starts, not at connection, as the
  revised prose says.
- The `mcp` 2.3.0 `MCPServer` application validates tool arguments against the
  Pydantic input model before the function runs (`ToolError` on a bad
  `period`), so the server-side model is the guarantee for MCP tools; the agent
  does not set `mcp_config` strict mode.
- `ToolCallJournal` with `id: Optional[int] = Field(default=None,
  primary_key=True)` autoincrements in sqlite, and sqlmodel 0.0.48 requires
  timezone-aware datetimes for `datetime` columns, so the journal writer uses
  `datetime.now(timezone.utc)`.

## audit_prep and MCP

`audit_prep` uses MCP servers, not plain function tools. The three servers are
real `mcp.server.mcpserver.MCPServer` applications (`audit_prep/servers.py`)
wrapped by `audit_prep/inprocess.py::InProcessMCPServer`, a subclass of the
SDK's abstract `agents.mcp.MCPServer` that calls `app.list_tools()` and
`app.call_tool()` directly instead of over a transport. The evidence store is
built with `require_approval={"publish_evidence_bundle": "always"}`, the same
keyword `MCPServerStreamableHttp` takes, because the adapter inherits that
parameter from the SDK base class. `tests/test_audit_prep.py` asserts that only
the publish tool carries the approval policy. The preview tool is named
`preview_evidence_bundle`. The `agent = Agent(...)` block in
`audit_prep/agent.py` is the chapter's, with `mcp_servers=[data_server,
policy_server, evidence_store]`.
