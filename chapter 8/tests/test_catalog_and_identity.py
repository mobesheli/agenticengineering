from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from agents import Agent, ToolInputGuardrailData
from agents.tool_context import ToolContext

from chapter8.catalog import DEFAULT_CATALOG, enforce_catalog
from chapter8.identity import (
    CLINICIAN_WRITE_SCOPE,
    clinician_read_session,
    clinician_write_session,
    require_active_session,
    scopes_for,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def test_read_and_write_phases_do_not_share_write_authority() -> None:
    read_scopes = scopes_for("read")
    assert "patient/MedicationRequest.rs" in read_scopes
    assert CLINICIAN_WRITE_SCOPE not in read_scopes
    assert scopes_for("write") == frozenset()


def test_catalog_allows_in_scope_read_and_rejects_write() -> None:
    session = clinician_read_session(
        clinician_ref="Practitioner/42",
        patient_id="synthetic-patient-001",
        now=NOW,
    )
    read = DEFAULT_CATALOG.evaluate(
        session=session,
        tool_name="read_medications",
        arguments={"patient_id": session.patient_id},
    )
    write = DEFAULT_CATALOG.evaluate(
        session=session,
        tool_name="write_reconciliation",
        arguments={"patient_id": session.patient_id},
    )
    assert read.allow is True
    assert write.allow is False
    assert write.behavior == "reject"
    assert write.missing_scopes == (CLINICIAN_WRITE_SCOPE,)


def test_catalog_halts_cross_patient_access() -> None:
    session = clinician_read_session(
        clinician_ref="Practitioner/42",
        patient_id="synthetic-patient-001",
        now=NOW,
    )
    decision = DEFAULT_CATALOG.evaluate(
        session=session,
        tool_name="read_medications",
        arguments={"patient_id": "synthetic-patient-002"},
    )
    assert decision.allow is False
    assert decision.behavior == "halt"
    assert decision.reason == "cross-patient access attempt"


def test_unregistered_agent_cannot_use_write_path() -> None:
    session = clinician_write_session(
        clinician_ref="Practitioner/42",
        patient_id="synthetic-patient-001",
        now=NOW,
    )
    session.agent_id = "unregistered-agent"
    decision = DEFAULT_CATALOG.evaluate(
        session=session,
        tool_name="write_reconciliation",
        arguments={"patient_id": session.patient_id},
    )
    assert decision.allow is False
    assert decision.behavior == "halt"


@pytest.mark.asyncio
async def test_sdk_guardrail_uses_application_context_not_model_text() -> None:
    session = clinician_read_session(
        clinician_ref="Practitioner/42",
        patient_id="synthetic-patient-001",
        now=NOW,
    )
    context = ToolContext(
        context=session,
        tool_name="read_medications",
        tool_call_id="call-1",
        tool_arguments=json.dumps({"patient_id": session.patient_id}),
    )
    result = await enforce_catalog(
        ToolInputGuardrailData(context=context, agent=Agent(name="reader"))
    )
    assert result.behavior["type"] == "allow"
    assert result.output_info["catalog_version"] == DEFAULT_CATALOG.version


@pytest.mark.asyncio
async def test_sdk_guardrail_halts_invalid_arguments() -> None:
    session = clinician_read_session(
        clinician_ref="Practitioner/42",
        patient_id="synthetic-patient-001",
        now=NOW,
    )
    context = ToolContext(
        context=session,
        tool_name="read_medications",
        tool_call_id="call-2",
        tool_arguments="not-json",
    )
    result = await enforce_catalog(
        ToolInputGuardrailData(context=context, agent=Agent(name="reader"))
    )
    assert result.behavior["type"] == "raise_exception"


def test_sessions_expire_and_write_session_is_narrow() -> None:
    session = clinician_write_session(
        clinician_ref="Practitioner/42",
        patient_id="synthetic-patient-001",
        now=NOW,
        ttl=timedelta(minutes=5),
    )
    assert session.granted_scopes == frozenset({CLINICIAN_WRITE_SCOPE})
    require_active_session(session, NOW + timedelta(minutes=4))
    with pytest.raises(PermissionError, match="expired"):
        require_active_session(session, NOW + timedelta(minutes=5))
