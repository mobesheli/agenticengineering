"""The tool-call journal: who did this, and what did they look at?

Every mutating call carries a deterministic idempotency key, and the
orchestration layer records every tool call with the identity behind it, a
hash of the validated arguments, the policy version in force, and the trace
identifier that links the row to the full run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, String, create_engine, select

JournalStatus = Literal["pending", "succeeded", "failed", "replayed"]


class ToolCallJournal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    trace_id: str = Field(index=True)
    tool_call_id: str = Field(unique=True)
    tool_name: str
    idempotency_key: str = Field(index=True)
    principal_id: str                  # authenticated human behind the run
    tenant_id: str
    on_behalf_of: Optional[str] = None # delegated identity, if any
    args_hash: str                     # sha256 of the validated arguments
    source_refs: str                   # identifiers of the records read
    policy_version: str                # reporting rules in force
    status: Literal["pending", "succeeded", "failed", "replayed"] = Field(sa_type=String)
    result_hash: Optional[str] = None
    materialized_object_id: Optional[str] = None
    approval_reference: Optional[str] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None


def stable_hash(payload: Any) -> str:
    """Return the sha256 of a JSON value with sorted keys."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def derive_call_key(*, run_id: str, tool_name: str, args_hash: str) -> str:
    """Derive the idempotency key for one tool call from the run and the intent."""
    material = f"{run_id}|{tool_name}|{args_hash}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


class Journal:
    """A small writer around the ``ToolCallJournal`` table.

    The default engine is an in-memory sqlite database, which is what the
    drills and tests want. Pass a URL such as ``sqlite:///journal.db`` to keep
    the rows.
    """

    def __init__(self, url: str = "sqlite://") -> None:
        self.engine: Engine = create_engine(url)
        SQLModel.metadata.create_all(self.engine)

    def record(
        self,
        *,
        run_id: str,
        trace_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: Any,
        principal_id: str,
        tenant_id: str,
        policy_version: str,
        status: JournalStatus,
        on_behalf_of: str | None = None,
        source_refs: list[str] | None = None,
        result: Any = None,
        materialized_object_id: str | None = None,
        approval_reference: str | None = None,
    ) -> ToolCallJournal:
        """Write one row for one tool call and return it."""
        args_hash = stable_hash(arguments)
        now = datetime.now(timezone.utc)
        row = ToolCallJournal(
            run_id=run_id,
            trace_id=trace_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            idempotency_key=derive_call_key(
                run_id=run_id, tool_name=tool_name, args_hash=args_hash
            ),
            principal_id=principal_id,
            tenant_id=tenant_id,
            on_behalf_of=on_behalf_of,
            args_hash=args_hash,
            source_refs=",".join(source_refs or []),
            policy_version=policy_version,
            status=status,
            result_hash=stable_hash(result) if result is not None else None,
            materialized_object_id=materialized_object_id,
            approval_reference=approval_reference,
            requested_at=now,
            completed_at=now if status != "pending" else None,
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
        return row

    def complete(
        self,
        tool_call_id: str,
        *,
        status: JournalStatus,
        result: Any = None,
        materialized_object_id: str | None = None,
        approval_reference: str | None = None,
    ) -> ToolCallJournal:
        """Close a row that was opened as pending while a call waited for approval."""
        with Session(self.engine) as session:
            statement = select(ToolCallJournal).where(
                ToolCallJournal.tool_call_id == tool_call_id
            )
            row = session.exec(statement).one()
            row.status = status
            row.result_hash = stable_hash(result) if result is not None else None
            row.materialized_object_id = materialized_object_id
            row.approval_reference = approval_reference
            row.completed_at = datetime.now(timezone.utc)
            session.add(row)
            session.commit()
            session.refresh(row)
        return row

    def rows(self, run_id: str) -> list[ToolCallJournal]:
        """Return every row for a run, in insertion order."""
        with Session(self.engine) as session:
            statement = (
                select(ToolCallJournal)
                .where(ToolCallJournal.run_id == run_id)
                .order_by(ToolCallJournal.id)
            )
            return list(session.exec(statement).all())
