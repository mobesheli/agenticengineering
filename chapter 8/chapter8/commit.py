"""The one path a write can take: policy, then the record server, then the record."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from agents.tracing import get_current_trace

from chapter8.approvals import ApprovalBook, action_hash
from chapter8.audit import DecisionLog, DecisionRecord
from chapter8.gateway import Gateway
from chapter8.policy import WritePolicy
from chapter8.records import Forbidden, RecordStore
from chapter8.session import Session
from chapter8.settings import AGENT_VERSION, MODELS


class Refused(Exception):
    """A deterministic control said no. The message is the rule that fired."""


@dataclass
class Committer:
    gateway: Gateway
    policy: WritePolicy
    store: RecordStore
    book: ApprovalBook
    log: DecisionLog
    _count: int = field(default=0)

    def _record(
        self,
        decision_id: str,
        kind: str,
        session: Session,
        tool: str,
        digest: str,
    ) -> DecisionRecord:
        trace = get_current_trace()
        return DecisionRecord(
            decision_id=decision_id,
            kind=kind,
            trace_id=trace.trace_id if trace else "no-trace",
            principal=session.clinician,
            delegation=[session.clinician, session.agent_id],
            agent_id=session.agent_id,
            agent_version=AGENT_VERSION,
            model_id=MODELS["writer"],
            policy_version=self.policy.limits.version,
            tool=tool,
            arguments_sha256=digest,
            rule="",
            recorded_at=self.gateway.clock(),
        )

    def commit(
        self, session: Session, tool: str, arguments: dict[str, Any]
    ) -> str:
        self._count += 1
        decision_id = f"d-{self._count:04d}"
        plain = json.dumps(arguments, sort_keys=True).encode()
        record = self._record(
            decision_id,
            "denied",
            session,
            tool,
            hashlib.sha256(plain).hexdigest(),
        )
        version = self.store.version(session.patient_id)
        decision = self.policy.authorize(session, tool, arguments, version)
        digest = action_hash(tool, arguments, session.patient_id)
        update = {"rule": decision.rule, "approver": self.book.approver(digest)}
        if not decision.allow:
            self.log.append(record.model_copy(update=update))
            raise Refused(decision.rule)
        self.log.append(
            record.model_copy(update={**update, "kind": "authorized"})
        )
        try:
            reference = self.store.update(session, arguments["changes"])
        except Forbidden as error:
            failed = {**update, "kind": "failed", "rule": str(error)}
            self.log.append(record.model_copy(update=failed))
            raise Refused(str(error)) from error
        self.book.spend(digest)
        done = {**update, "kind": "executed", "business_ref": reference}
        self.log.append(record.model_copy(update=done))
        self.gateway.events.append(
            "write_executed", session.agent_id, tool, reference
        )
        return reference
