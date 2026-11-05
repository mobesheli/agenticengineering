"""Run the audit-prep evidence flow end to end, offline.

    python -m audit_prep.main

The orchestration layer authenticates the control owner, builds the run
context, connects the three MCP servers in process, and runs the agent. The
model is the SDK's scripted test double, so the run needs no key: it pulls the
snapshot and the journal sample, fetches the reporting requirements, drafts the
bundle, writes three artifacts, and stops at ``publish_evidence_bundle`` with
one interruption. A scripted reviewer approves, the run resumes, and every tool
call ends up in the journal with the principal, the argument hash, and the
policy version.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agents import Runner, RunResult, set_tracing_disabled
from agents.testing import ModelCall, ModelStep, ScriptedModel, assistant_message, function_call
from agents.tracing import gen_trace_id

from audit_prep.agent import build_agent
from audit_prep.models import AuditRunContext, EvidenceBundleStatus, EvidenceRequest
from audit_prep.servers import data_server, evidence_store, policy_server
from ch3.approvals import ScriptedReviewer, pending_arguments
from ch3.journal import Journal, JournalStatus

set_tracing_disabled(True)  # scripted runs never call the API, so there is nothing to export

REQUEST = EvidenceRequest(control_id="LIQ-07", period="2026-Q3", jurisdiction="uk")
PRINCIPAL = "control.owner@example.com"
TENANT = "acme-uk"
RUN_ID = "run_ae_0007"


def last_tool_output(call: ModelCall) -> dict[str, Any]:
    """Read the most recent tool result the model was shown, as a dictionary."""
    for item in reversed(call.input):
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            output = item["output"]
            if isinstance(output, list):
                output = "".join(part.get("text", "") for part in output)
            return json.loads(output)
    raise LookupError("no tool output in the conversation yet")


def scripted_flow() -> ScriptedModel:
    """What a well-behaved model does on this task, step by step.

    Later steps read the bundle identifier and the bundle hash from earlier
    tool results, the way a real model would, instead of hard-coding them.
    """

    def write(kind: str, content: str, call_id: str):
        def step(call: ModelCall):
            bundle_id = last_tool_output(call)["bundle_id"]
            return [function_call("write_evidence_artifact",
                                  {"bundle_id": bundle_id, "kind": kind, "content": content},
                                  call_id=call_id)]
        return ModelStep.respond(step)

    def publish(call: ModelCall):
        last = last_tool_output(call)
        return [function_call("publish_evidence_bundle",
                              {"bundle_id": last["bundle_id"], "content_hash": last["bundle_hash"]},
                              call_id="call_8")]

    def final(call: ModelCall):
        last = last_tool_output(call)
        status = EvidenceBundleStatus(bundle_id=last["bundle_id"], status="published",
                                      artifact_count=3)
        return [assistant_message(status.model_dump_json())]

    return ScriptedModel([
        [function_call("get_trial_balance_snapshot",
                       {"query": {"period": "2026-Q3", "entity": "UK01",
                                  "materiality_threshold": 1_000_000}}, call_id="call_1")],
        [function_call("get_journal_entries",
                       {"period": "2026-Q3", "above_amount": 1_000_000, "cursor": 0,
                        "page_size": 3}, call_id="call_2")],
        [function_call("get_reporting_requirements",
                       {"jurisdiction": "uk", "report_type": "liquidity",
                        "effective_date": "2026-09-30"}, call_id="call_3")],
        [function_call("preview_evidence_bundle",
                       {"control_id": "LIQ-07", "period": "2026-Q3"}, call_id="call_4")],
        write("trial_balance", "UK01 2026-Q3 trial balance, 6 accounts above 1,000,000", "call_5"),
        write("journal_sample", "JE-20931, JE-21040 sampled above materiality", "call_6"),
        write("requirements_extract", "rules-2026.07, uk liquidity reporting, 3 artifacts", "call_7"),
        ModelStep.respond(publish),
        ModelStep.respond(final),
    ])


class RunJournaler:
    """Write one journal row per tool call, across an interrupted and resumed run.

    A resumed run reports every item from the start of the run, so the
    journaler remembers which calls it has already written and only closes the
    row of a call that was waiting for approval.
    """

    def __init__(self, journal: Journal, ctx: AuditRunContext, trace_id: str) -> None:
        self.journal = journal
        self.ctx = ctx
        self.trace_id = trace_id
        self.recorded: set[str] = set()
        self.awaiting: set[str] = set()

    def record(self, result: RunResult) -> None:
        calls: dict[str, tuple[str, Any]] = {}
        for item in result.new_items:
            if item.type == "tool_call_item":
                raw = item.raw_item
                calls[raw.call_id] = (raw.name, json.loads(raw.arguments or "{}"))
        for item in result.new_items:
            if item.type == "tool_call_output_item":
                call_id = item.raw_item["call_id"]
                output = item.output
                text = output["text"] if isinstance(output, dict) else str(output)
                payload = json.loads(text)
                if call_id in self.awaiting:
                    self.journal.complete(call_id, status=_status_of(payload), result=payload,
                                          materialized_object_id=payload.get("bundle_id"),
                                          approval_reference="approved by reviewer")
                    self.awaiting.discard(call_id)
                    continue
                if call_id in self.recorded:
                    continue
                name, arguments = calls[call_id]
                if name == "get_reporting_requirements" and payload.get("policy_version"):
                    self.ctx.policy_version = payload["policy_version"]
                self._open(call_id, name, arguments, status=_status_of(payload), payload=payload)
            elif item.type == "tool_approval_item":
                call_id = item.raw_item.call_id
                if call_id in self.recorded:
                    continue
                name, arguments = calls[call_id]
                self._open(call_id, name, arguments, status="pending", payload=None)
                self.awaiting.add(call_id)

    def _open(self, call_id: str, name: str, arguments: Any, *, status: JournalStatus,
              payload: dict[str, Any] | None) -> None:
        self.journal.record(
            run_id=self.ctx.run_id, trace_id=self.trace_id, tool_call_id=call_id,
            tool_name=name, arguments=arguments, principal_id=self.ctx.principal_id,
            tenant_id=self.ctx.tenant_id, on_behalf_of=self.ctx.on_behalf_of,
            policy_version=self.ctx.policy_version, status=status,
            source_refs=_source_refs(payload or {}), result=payload,
            materialized_object_id=(payload or {}).get("bundle_id"),
        )
        self.recorded.add(call_id)


def _status_of(payload: dict[str, Any]) -> JournalStatus:
    """Map a tool result onto the journal's status vocabulary."""
    if not payload.get("ok", True):
        return "failed"
    if payload.get("replayed"):
        return "replayed"
    return "succeeded"


def _source_refs(payload: dict[str, Any]) -> list[str]:
    refs = payload.get("source_refs") or ([payload["source_ref"]] if "source_ref" in payload else [])
    return list(refs)


async def run_evidence_flow(
    request: EvidenceRequest, *, principal_id: str, tenant_id: str, run_id: str
) -> tuple[EvidenceBundleStatus, Journal, AuditRunContext]:
    """The orchestration layer: context, servers, agent, approval, journal."""
    ctx = AuditRunContext(run_id=run_id, principal_id=principal_id, tenant_id=tenant_id,
                          request=request)
    journal = Journal()
    trace_id = gen_trace_id()
    journaler = RunJournaler(journal, ctx, trace_id)
    reviewer = ScriptedReviewer(approve=True)
    model = scripted_flow()

    async with data_server() as data, policy_server() as policy, evidence_store() as evidence:
        for server in (data, policy, evidence):
            tools = await server.list_tools()
            noun = "tool" if len(tools) == 1 else "tools"
            print(f"server     : {server.name} ({len(tools)} {noun})")
        agent = build_agent(data, policy, evidence, model=model)
        task = (f"Assemble the evidence bundle for control {request.control_id}, "
                f"period {request.period}, jurisdiction {request.jurisdiction}.")
        result = await Runner.run(agent, task, context=ctx)
        journaler.record(result)
        names = [i.raw_item.name for i in result.new_items if i.type == "tool_call_item"]
        print(f"tool calls : {', '.join(names)}")
        while result.interruptions:
            state = result.to_state()
            for item in result.interruptions:
                args = pending_arguments(item)
                print(f"interrupt  : {item.name}(bundle_id={args['bundle_id']}, "
                      f"content_hash={args['content_hash']})")
                decision = await reviewer.decide(item)
                print(f"reviewer   : {'approved' if decision.approved else 'rejected'}")
                if decision.approved:
                    state.approve(item)
                else:
                    state.reject(item, rejection_message=decision.reason)
            result = await Runner.run(agent, state)
            journaler.record(result)
        model.assert_complete()
    return result.final_output, journal, ctx


async def main() -> None:
    print(f"run        : {RUN_ID} principal={PRINCIPAL} tenant={TENANT}")
    status, journal, ctx = await run_evidence_flow(
        REQUEST, principal_id=PRINCIPAL, tenant_id=TENANT, run_id=RUN_ID
    )
    print(f"final      : bundle {status.bundle_id} {status.status}, "
          f"{status.artifact_count} artifacts")
    rows = journal.rows(ctx.run_id)
    print(f"journal    : {len(rows)} rows")
    for row in rows:
        approval = f" approval={row.approval_reference}" if row.approval_reference else ""
        print(f"  {row.tool_name:<27} {row.status:<9} principal={row.principal_id} "
              f"args={row.args_hash[:8]} policy={row.policy_version}{approval}")


if __name__ == "__main__":
    asyncio.run(main())
