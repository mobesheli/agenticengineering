from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from chapter8.governance import (
    CapturingProcessor,
    GovernedMemory,
    RedactingProcessor,
    TraceRedactor,
    find_canary_leaks,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def test_trace_redactor_masks_personal_fields_secrets_and_note_content() -> None:
    note = "A synthetic clinical note that must not reach the trace store."
    redactor = TraceRedactor(known_personal_values={"Jordan Example"})
    scrubbed = redactor.scrub(
        {
            "patient_name": "Jordan Example",
            "summary": "Jordan Example presented for review",
            "authorization": "Bearer private-value",
            "text": note,
        }
    )
    assert scrubbed["patient_name"] == "[redacted]"
    assert "Jordan Example" not in scrubbed["summary"]
    assert scrubbed["authorization"] == "[secret]"
    assert scrubbed["text"].startswith("sha256:")
    assert find_canary_leaks(scrubbed, {note, "Jordan Example"}) == []


@dataclass
class SpanData:
    input: object
    output: object


@dataclass
class Span:
    span_data: SpanData


def test_redacting_processor_scrubs_before_forwarding() -> None:
    downstream = CapturingProcessor()
    processor = RedactingProcessor(downstream)
    span = Span(SpanData(input={"mrn": "SYNTH-1"}, output={"text": "note"}))
    processor.on_span_end(span)
    forwarded = downstream.spans[-1][1]
    assert forwarded.span_data.input["mrn"] == "[redacted]"
    assert forwarded.span_data.output["text"].startswith("sha256:")


def test_governed_memory_requires_review_scopes_reads_and_emits_receipt() -> None:
    memory = GovernedMemory()
    with pytest.raises(PermissionError, match="requires review"):
        memory.write(
            subject_id="patient-1",
            category="preference",
            value="brand A",
            approved=False,
        )
    memory.write(
        subject_id="patient-1",
        category="preference",
        value="brand A",
        approved=True,
    )
    memory.write(
        subject_id="patient-2",
        category="preference",
        value="brand B",
        approved=True,
    )
    assert len(memory.read("patient-1")) == 1
    assert "brand B" not in str(memory.read("patient-1"))
    receipt = memory.purge("patient-1", now=NOW)
    assert receipt.deleted_entries == 1
    assert memory.read("patient-1") == ()
    assert len(receipt.receipt_hash) == 64
