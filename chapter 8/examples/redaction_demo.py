"""The canary test: run the reader on a patient whose record is full of canaries,
export the trace twice, and count the canaries that reached each destination.

    python -m examples.redaction_demo           scripted model, no API key needed
    python -m examples.redaction_demo --live    live model, needs OPENAI_API_KEY

In the live run nothing is sent to the provider's trace backend, because the
example replaces the SDK's trace processors with its own two.
"""

from __future__ import annotations

import asyncio
import json
import sys

from agents.tracing import set_trace_processors
from agents.tracing.processors import BatchTraceProcessor

from chapter8.harness import Harness
from chapter8.phases import read_phase
from chapter8.redaction import RawExporter, RedactingExporter, find_canaries
from examples import scripted
from examples.scripted import CLINICIAN

CANARIES = {
    "CANARY-DOSE-9021",
    "CANARY-ALLERGEN-3306",
    "CANARY-NOTE-4417",
    "CANARY-TOKEN-5555",
}


async def run(live: bool = False) -> dict[str, list]:
    raw: list[dict] = []
    redacted: list[dict] = []
    key = b"example-trace-key"
    processors = [
        BatchTraceProcessor(RawExporter(raw.append), schedule_delay=0.05),
        BatchTraceProcessor(
            RedactingExporter(redacted.append, key), schedule_delay=0.05
        ),
    ]
    set_trace_processors(processors)
    harness = Harness.build()
    session = harness.tokens.launch("read", CLINICIAN, "pt-1003")
    reader = harness.reader(None if live else scripted.reader_canary())
    await read_phase(reader, session, harness.store)
    for processor in processors:
        processor.force_flush()
    events = [
        event.__dict__ for event in harness.events.of_kind("policy_denied")
    ]
    decisions = [record.model_dump() for record in harness.log.records()]
    return {
        "trace export, no redaction": raw,
        "trace export, redacted": redacted,
        "gateway event log": events,
        "decision log": decisions,
        "record server audit events": harness.store.audit,
    }


def main() -> None:
    destinations = asyncio.run(run(live="--live" in sys.argv))
    print(f"{'destination':<29}{'items':<7}canaries found")
    for name, payload in destinations.items():
        found = find_canaries(payload, CANARIES)
        print(f"{name:<29}{len(payload):<7}{len(found)} of {len(CANARIES)}")
    spans = destinations["trace export, redacted"]
    sample = next(
        s for s in spans if s.get("span_data", {}).get("type") == "function"
    )
    shown = {**sample["span_data"]}
    for field in ("input", "output"):
        shown[field] = {
            **shown[field],
            "hmac_sha256": shown[field]["hmac_sha256"][:12],
        }
    print("one redacted tool span:")
    print(json.dumps(shown, indent=2))


if __name__ == "__main__":
    main()
