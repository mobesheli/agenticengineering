"""The write phase: receives a typed proposal, never a note, and one gated tool."""

from __future__ import annotations

from agents import Agent, Model, RunContextWrapper, function_tool

from chapter8.catalog import catalog_guardrail
from chapter8.commit import Committer
from chapter8.gateway import Gateway
from chapter8.proposal import WriteArguments, WriteChange
from chapter8.reader import explain
from chapter8.session import Session
from chapter8.settings import MODELS

WRITER_INSTRUCTIONS = """
You record a medication reconciliation that a clinician will approve.

The input is a JSON object with a patient, a record version, and a list of changes.
Write a chart note of at most three sentences that states each change in plain
clinical language, using only the information in the input. Then call
write_reconciliation once with the patient, the record version, the changes exactly
as given (action, target, and reason for each), and your note.

When the tool returns a record reference, the write is done: report the reference
in one sentence. If the tool is refused, say that nothing was written and give the
reason. Do not call the tool a second time.
""".strip()


def build_writer(
    gateway: Gateway, committer: Committer, model: str | Model | None = None
) -> Agent[Session]:
    @function_tool(
        needs_approval=True,
        tool_input_guardrails=[catalog_guardrail(gateway)],
        failure_error_function=explain,
    )
    def write_reconciliation(
        ctx: RunContextWrapper[Session],
        patient_id: str,
        record_version: int,
        changes: list[WriteChange],
        note: str,
    ) -> str:
        """Apply an approved reconciliation to the patient's medication list."""
        arguments = WriteArguments(
            patient_id=patient_id,
            record_version=record_version,
            changes=changes,
            note=note,
        )
        session = ctx.context
        return committer.commit(
            session, "write_reconciliation", arguments.model_dump()
        )

    return Agent(
        name="reconciliation-writer",
        instructions=WRITER_INSTRUCTIONS,
        tools=[write_reconciliation],
        model=model or MODELS["writer"],
    )
