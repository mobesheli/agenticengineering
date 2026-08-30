"""Run the secured medication-reconciliation pattern."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from .evidence import emit_security_evidence
from .identity import clinician_read_session, clinician_write_session
from .live import build_read_agent, run_live_read
from .reconciliation import SyntheticRecordStore, load_fixture
from .runtime import SecurityHarness


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Chapter 8 security harness.")
    parser.add_argument(
        "--fixture",
        choices=("clean", "hostile_note"),
        default="hostile_note",
    )
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--show-live-wiring", action="store_true")
    return parser


async def _run_live(fixture_name: str) -> None:
    patient = load_fixture(fixture_name)
    store = SyntheticRecordStore([patient])
    now = datetime.now(timezone.utc)
    session = clinician_read_session(
        clinician_ref="Practitioner/clinician-042",
        patient_id=patient.patient_id,
        now=now,
        trace_id="trace-live-read",
    )
    result = await run_live_read(store, session)
    print(result.model_dump_json(indent=2))


def _run_offline(fixture_name: str, evidence_dir: Path | None) -> None:
    patient = load_fixture(fixture_name)
    now = datetime.now(timezone.utc)
    harness = SecurityHarness(patient, clock=lambda: now)
    clinician_ref = "Practitioner/clinician-042"
    read_session = clinician_read_session(
        clinician_ref=clinician_ref,
        patient_id=patient.patient_id,
        now=now,
        trace_id="trace-chapter-8-demo",
    )
    proposal = harness.propose(read_session)
    grant = harness.approve(
        proposal,
        approver=clinician_ref,
        approver_role="clinician",
        narrative="Review the itemized medication changes and supporting evidence.",
    )
    write_session = clinician_write_session(
        clinician_ref=clinician_ref,
        patient_id=patient.patient_id,
        now=now,
        trace_id=read_session.trace_id,
    )
    write_session.approvals[grant.action_hash] = grant
    outcome = harness.commit(proposal, write_session=write_session)
    if evidence_dir:
        emit_security_evidence(harness, outcome, evidence_dir)
    report = {
        "fixture": fixture_name,
        "proposal": proposal.model_dump(mode="json"),
        "outcome": outcome.model_dump(mode="json"),
        "audit_chain_verified": harness.decisions.verify(),
        "privacy_canary": harness.privacy_canary_report(),
        "evidence_dir": str(evidence_dir) if evidence_dir else None,
    }
    print(json.dumps(report, indent=2, default=str))


def main() -> None:
    args = _parser().parse_args()
    patient = load_fixture(args.fixture)
    if args.show_live_wiring:
        agent = build_read_agent(SyntheticRecordStore([patient]))
        wiring = {
            "name": agent.name,
            "model": agent.model,
            "tools": [tool.name for tool in agent.tools],
            "tool_guardrails": {
                tool.name: len(getattr(tool, "tool_input_guardrails", []))
                for tool in agent.tools
            },
        }
        print(json.dumps(wiring, indent=2))
        return
    if args.live:
        try:
            asyncio.run(_run_live(args.fixture))
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        return
    _run_offline(args.fixture, args.evidence_dir)


if __name__ == "__main__":
    main()
