"""Trace redaction, privacy canaries, and governed memory."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from typing import Any

from agents.tracing import TracingProcessor

from .models import DeletionReceipt

SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]{8,}|authorization:\s*\S+)"
)
PERSONAL_FIELDS = {
    "patient_name",
    "date_of_birth",
    "mrn",
    "address",
    "phone",
}
HASHED_CONTENT_FIELDS = {"clinical_note", "content", "note_text", "text"}
LONG_TEXT_LIMIT = 2000


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TraceRedactor:
    def __init__(
        self,
        *,
        known_personal_values: set[str] | None = None,
        long_text_limit: int = LONG_TEXT_LIMIT,
    ) -> None:
        self.known_personal_values = {
            value for value in (known_personal_values or set()) if value
        }
        self.long_text_limit = long_text_limit

    def scrub(self, value: Any) -> Any:
        if isinstance(value, dict):
            scrubbed: dict[str, Any] = {}
            for key, item in value.items():
                normalized = key.casefold()
                if normalized in PERSONAL_FIELDS:
                    scrubbed[key] = "[redacted]"
                elif normalized in HASHED_CONTENT_FIELDS and isinstance(item, str):
                    scrubbed[key] = f"sha256:{sha256_text(item)}"
                else:
                    scrubbed[key] = self.scrub(item)
            return scrubbed
        if isinstance(value, list):
            return [self.scrub(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.scrub(item) for item in value)
        if not isinstance(value, str):
            return value
        text = SECRET_PATTERN.sub("[secret]", value)
        for personal_value in sorted(self.known_personal_values, key=len, reverse=True):
            text = re.sub(re.escape(personal_value), "[personal]", text, flags=re.IGNORECASE)
        if len(text) > self.long_text_limit:
            return f"sha256:{sha256_text(text)}"
        return text


class CapturingProcessor(TracingProcessor):
    def __init__(self) -> None:
        self.traces: list[Any] = []
        self.spans: list[Any] = []

    def on_trace_start(self, trace: Any) -> None:
        self.traces.append(("start", trace))

    def on_trace_end(self, trace: Any) -> None:
        self.traces.append(("end", trace))

    def on_span_start(self, span: Any) -> None:
        self.spans.append(("start", deepcopy(span)))

    def on_span_end(self, span: Any) -> None:
        self.spans.append(("end", deepcopy(span)))

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None


class RedactingProcessor(TracingProcessor):
    def __init__(
        self,
        downstream: TracingProcessor,
        redactor: TraceRedactor | None = None,
    ) -> None:
        self.downstream = downstream
        self.redactor = redactor or TraceRedactor()

    def on_trace_start(self, trace: Any) -> None:
        self.downstream.on_trace_start(trace)

    def on_trace_end(self, trace: Any) -> None:
        self.downstream.on_trace_end(trace)

    def on_span_start(self, span: Any) -> None:
        self.downstream.on_span_start(span)

    def on_span_end(self, span: Any) -> None:
        data = span.span_data
        if getattr(data, "input", None) is not None:
            data.input = self.redactor.scrub(data.input)
        if getattr(data, "output", None) is not None:
            data.output = self.redactor.scrub(data.output)
        self.downstream.on_span_end(span)

    def shutdown(self) -> None:
        self.downstream.shutdown()

    def force_flush(self) -> None:
        self.downstream.force_flush()


def find_canary_leaks(payload: Any, canaries: set[str]) -> list[str]:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return sorted(canary for canary in canaries if canary in serialized)


class GovernedMemory:
    def __init__(self) -> None:
        self._entries: dict[str, list[dict[str, Any]]] = {}

    def write(
        self,
        *,
        subject_id: str,
        category: str,
        value: str,
        approved: bool,
    ) -> None:
        if not approved:
            raise PermissionError("persistent memory write requires review")
        entry = {
            "category": category,
            "value": value,
            "value_hash": sha256_text(value),
        }
        self._entries.setdefault(subject_id, []).append(entry)

    def read(self, subject_id: str) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._entries.get(subject_id, [])))

    def purge(self, subject_id: str, *, now: datetime) -> DeletionReceipt:
        deleted = len(self._entries.pop(subject_id, []))
        payload = f"{subject_id}:{deleted}:{now.isoformat()}"
        return DeletionReceipt(
            subject_id=subject_id,
            deleted_entries=deleted,
            completed_at=now,
            receipt_hash=sha256_text(payload),
        )
