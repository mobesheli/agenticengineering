"""Complete deterministic security harness for medication reconciliation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .approvals import ApprovalBook, action_hash, lint_approval_request
from .audit import DecisionChain, DecisionRecord, audit_event, hash_arguments
from .catalog import DEFAULT_CATALOG, ToolCatalog
from .governance import TraceRedactor, find_canary_leaks
from .identity import require_active_session
from .models import (
    ApprovalGrant,
    LintResult,
    PatientFixture,
    ReconciliationProposal,
    SecurityOutcome,
    SessionContext,
)
from .policy import EventHistory, SecurityEvent, WritePolicy
from .reconciliation import QuarantinedReader, SyntheticRecordStore
from .registry import AgentRegistry

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "policies" / "write_policy_v1.json"


class SecurityHarness:
    def __init__(
        self,
        patient: PatientFixture,
        *,
        clock: Callable[[], datetime] | None = None,
        catalog: ToolCatalog = DEFAULT_CATALOG,
        max_writes_per_hour: int = 5,
    ) -> None:
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.catalog = catalog
        self.policy_config = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.store = SyntheticRecordStore([patient])
        self.reader = QuarantinedReader(self.store)
        self.approvals = ApprovalBook()
        self.history = EventHistory()
        self.policy = WritePolicy(self.history, max_writes_per_hour=max_writes_per_hour)
        self.registry = AgentRegistry()
        self.decisions = DecisionChain()
        self.fhir_audit_events: list[dict[str, Any]] = []
        self.redactor = TraceRedactor(
            known_personal_values={patient.patient_name, patient.date_of_birth, patient.mrn}
        )

    @property
    def agent_id(self) -> str:
        return "medication-reconciliation-agent"

    def propose(self, session: SessionContext) -> ReconciliationProposal:
        now = self.clock()
        self.registry.require_enabled(session.agent_id)
        require_active_session(session, now)
        for tool_name in ("read_medications", "read_fills", "check_interactions"):
            decision = self.catalog.evaluate(
                session=session,
                tool_name=tool_name,
                arguments={"patient_id": session.patient_id}
                if tool_name != "check_interactions"
                else {},
            )
            if not decision.allow:
                raise PermissionError(decision.reason)
        proposal = self.reader.build_proposal(session.patient_id, now=now)
        for resource in ("MedicationRequest", "MedicationDispense"):
            self.fhir_audit_events.append(
                audit_event(
                    session.agent_id,
                    session.clinician_ref,
                    f"Patient/{session.patient_id}",
                    "R",
                    f"{resource}/{session.patient_id}",
                    "0",
                    recorded_at=now,
                )
            )
        return proposal

    def review_request(
        self,
        proposal: ReconciliationProposal,
        narrative: str,
    ) -> LintResult:
        return lint_approval_request(narrative, len(proposal.changes))

    def approve(
        self,
        proposal: ReconciliationProposal,
        *,
        approver: str,
        approver_role: str,
        narrative: str,
    ) -> ApprovalGrant:
        lint = self.review_request(proposal, narrative)
        if not lint.present_to_reviewer:
            raise PermissionError(f"approval request requires review: {', '.join(lint.flags)}")
        params = proposal.write_arguments()
        now = self.clock()
        grant = self.approvals.grant(
            tool_name="write_reconciliation",
            params=params,
            approver=approver,
            approver_role=approver_role,
            now=now,
        )
        self.history.append(
            SecurityEvent(
                agent_id=self.agent_id,
                event_type="approval_granted",
                occurred_at=now,
                action_hash=grant.action_hash,
                details=(("approver", approver), ("role", approver_role)),
            )
        )
        return grant

    def commit(
        self,
        proposal: ReconciliationProposal,
        *,
        write_session: SessionContext,
    ) -> SecurityOutcome:
        now = self.clock()
        self.registry.require_enabled(self.agent_id)
        require_active_session(write_session, now)
        params = proposal.write_arguments()
        digest = action_hash("write_reconciliation", params)
        if write_session.patient_id != proposal.patient_id:
            return self._deny(
                proposal,
                write_session,
                digest,
                "cross-patient write attempt",
                now,
            )
        catalog_decision = self.catalog.evaluate(
            session=write_session,
            tool_name="write_reconciliation",
            arguments=params,
        )
        if not catalog_decision.allow:
            return self._deny(
                proposal,
                write_session,
                digest,
                catalog_decision.reason,
                now,
            )
        try:
            grant = self.approvals.require(
                tool_name="write_reconciliation",
                params=params,
                now=now,
                role="clinician",
                principal=write_session.clinician_ref,
            )
        except PermissionError as exc:
            return self._deny(proposal, write_session, digest, str(exc), now)
        policy_args = {**params, "action_hash": digest}
        policy_decision = self.policy.evaluate(
            self.agent_id,
            "write_reconciliation",
            policy_args,
            now,
        )
        if not policy_decision.allow:
            return self._deny(
                proposal,
                write_session,
                digest,
                policy_decision.rule,
                now,
                approver=grant.approver,
            )
        business_ref = self.store.apply(
            proposal,
            clinician_ref=write_session.clinician_ref,
        )
        self.history.append(
            SecurityEvent(
                agent_id=self.agent_id,
                event_type="write_executed",
                occurred_at=now,
                action_hash=digest,
                details=(("business_record_ref", business_ref),),
            )
        )
        record_hash = self._record_decision(
            proposal=proposal,
            session=write_session,
            digest=digest,
            decision="allow",
            rule=policy_decision.rule,
            now=now,
            approver=grant.approver,
            outcome="committed",
            business_ref=business_ref,
        )
        event = audit_event(
            self.agent_id,
            write_session.clinician_ref,
            f"Patient/{proposal.patient_id}",
            "C",
            business_ref,
            "0",
            recorded_at=now,
        )
        self.fhir_audit_events.append(event)
        return SecurityOutcome(
            status="committed",
            patient_id=proposal.patient_id,
            action_hash=digest,
            policy_rule=policy_decision.rule,
            business_record_ref=business_ref,
            decision_record_hash=record_hash,
            audit_event=event,
        )

    def stop(self, reason: str) -> None:
        self.registry.stop(self.agent_id, reason=reason, now=self.clock())

    def privacy_canary_report(self) -> dict[str, Any]:
        patient = self.store.patient(self.store.patient_ids[0])
        payload = self.redactor.scrub(patient.model_dump(mode="json"))
        canaries = {
            patient.patient_name,
            patient.date_of_birth,
            patient.mrn,
            *(note.text for note in patient.notes),
        }
        leaks = find_canary_leaks(payload, canaries)
        return {"passed": not leaks, "leaks": leaks, "redacted_sample": payload}

    def _deny(
        self,
        proposal: ReconciliationProposal,
        session: SessionContext,
        digest: str,
        rule: str,
        now: datetime,
        *,
        approver: str | None = None,
    ) -> SecurityOutcome:
        record_hash = self._record_decision(
            proposal=proposal,
            session=session,
            digest=digest,
            decision="deny",
            rule=rule,
            now=now,
            approver=approver,
            outcome="denied",
        )
        return SecurityOutcome(
            status="denied",
            patient_id=proposal.patient_id,
            action_hash=digest,
            policy_rule=rule,
            decision_record_hash=record_hash,
        )

    def _record_decision(
        self,
        *,
        proposal: ReconciliationProposal,
        session: SessionContext,
        digest: str,
        decision: str,
        rule: str,
        now: datetime,
        approver: str | None,
        outcome: str,
        business_ref: str | None = None,
    ) -> str:
        record = DecisionRecord(
            record_id=f"decision-{len(self.decisions.records) + 1:04d}",
            prev_hash=self.decisions.head_hash,
            trace_id=session.trace_id or proposal.proposal_id,
            principal=session.principal,
            delegation_chain=list(session.delegation_chain),
            agent_id=self.agent_id,
            agent_version="8.0.0",
            model_id="deterministic-quarantined-reader",
            policy_bundle_version=self.policy_config["version"],
            tool_name="write_reconciliation",
            args_hash=hash_arguments(proposal.write_arguments()),
            policy_decision=decision,
            policy_rule=rule,
            approver=approver,
            outcome=outcome,
            business_record_ref=business_ref,
            retention_class=self.policy_config["retention_class"],
            recorded_at=now,
        )
        return self.decisions.append(record)
