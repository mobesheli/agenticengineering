"""Redact traces in the last code that runs before they leave the process.

The exporter keeps an allowlist of structural fields and replaces everything else
with a keyed fingerprint. Content never reaches the trace store, and two spans that
carried the same content can still be matched.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any

from agents.tracing import Span, Trace
from agents.tracing.processor_interface import TracingExporter

KEEP = frozenset(
    {
        "object",
        "id",
        "trace_id",
        "parent_id",
        "started_at",
        "ended_at",
        "workflow_name",
    }
)
SPAN_KEEP = frozenset(
    {
        "type",
        "name",
        "model",
        "usage",
        "tools",
        "handoffs",
        "output_type",
        "triggered",
    }
)


def fingerprint(value: object, key: bytes) -> dict[str, object]:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    digest = hmac.new(key, text.encode(), hashlib.sha256).hexdigest()
    return {"hmac_sha256": digest, "chars": len(text)}


def scrub(item: dict[str, Any], key: bytes) -> dict[str, Any]:
    clean = {name: value for name, value in item.items() if name in KEEP}
    data = item.get("span_data") or {}
    clean["span_data"] = {
        name: value if name in SPAN_KEEP else fingerprint(value, key)
        for name, value in data.items()
        if value is not None
    }
    if item.get("error"):
        clean["error"] = fingerprint(item["error"], key)
    return clean


class RedactingExporter(TracingExporter):
    def __init__(
        self, send: Callable[[dict[str, Any]], None], key: bytes
    ) -> None:
        self.send = send
        self.key = key

    def export(self, items: list[Trace | Span[Any]]) -> None:
        for item in items:
            exported = item.export()
            if exported is not None:
                self.send(scrub(exported, self.key))


class RawExporter(TracingExporter):
    """What an exporter sends when nobody redacts. Used only to show the difference."""

    def __init__(self, send: Callable[[dict[str, Any]], None]) -> None:
        self.send = send

    def export(self, items: list[Trace | Span[Any]]) -> None:
        for item in items:
            exported = item.export()
            if exported is not None:
                self.send(exported)


def find_canaries(payload: object, canaries: set[str]) -> list[str]:
    """The canary values that appear anywhere in a payload."""
    text = json.dumps(payload, default=str)
    return sorted(canary for canary in canaries if canary in text)
