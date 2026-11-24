"""What the clinician sees: the evidence first, the agent's prose last and linted."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from chapter8.linter import LintResult, lint_approval_request
from chapter8.phases import Parked
from chapter8.records import RecordStore


@dataclass
class Review:
    lines: list[str]
    lint: LintResult
    approvable: bool


def build_review(parked: Parked, store: RecordStore, clinician: str) -> Review:
    proposal, ask = parked.proposal, parked.asks[0]
    header = f"Review for Patient/{proposal.patient_id}, record version"
    lines = [f"{header} {proposal.record_version}, requested for {clinician}"]
    evidence_chars = 0
    for number, change in enumerate(proposal.changes, start=1):
        item = store.medication(proposal.patient_id, change.target)
        label = f"{item.name} {item.dose}" if item else change.target
        evidence = ", ".join(change.evidence)
        lines.append(f"  {number}. {change.action:<16}{label}")
        lines.append(f"     reason          {change.reason}")
        lines.extend(
            textwrap.wrap(
                evidence,
                width=78,
                initial_indent="     evidence        ",
                subsequent_indent=" " * 21,
            )
        )
        evidence_chars += len(label) + len(evidence) + len(change.reason)
    note = ask.arguments.note if ask.arguments else ""
    itemized = len(ask.arguments.changes) if ask.arguments else 0
    lint = lint_approval_request(
        note, len(proposal.changes), itemized, evidence_chars
    )
    flags = ", ".join(lint.flags) or "clean"
    lines.append(
        f"  note              collapsed, {len(note)} characters, lint: {flags}"
    )
    if ask.problem:
        lines.append(f"  cannot be approved: {ask.problem}")
    else:
        lines.append(f"  action sha256     {ask.digest[:16]}")
    return Review(lines, lint, approvable=not ask.problem)
