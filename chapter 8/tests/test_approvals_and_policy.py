from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from chapter8.approvals import ApprovalBook, action_hash, lint_approval_request
from chapter8.policy import EventHistory, SecurityEvent, WritePolicy

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def params(change_count: int = 1) -> dict:
    return {
        "patient_id": "synthetic-patient-001",
        "changes": [{"code": str(index)} for index in range(change_count)],
        "rationale": "itemized review",
    }


def test_action_hash_is_stable_and_bound_to_exact_parameters() -> None:
    first = action_hash("write_reconciliation", {"b": 2, "a": 1})
    second = action_hash("write_reconciliation", {"a": 1, "b": 2})
    changed = action_hash("write_reconciliation", {"a": 1, "b": 3})
    assert first == second
    assert changed != first


def test_approval_checks_role_principal_and_expiry() -> None:
    book = ApprovalBook()
    grant = book.grant(
        tool_name="write_reconciliation",
        params=params(),
        approver="Practitioner/42",
        approver_role="clinician",
        now=NOW,
    )
    assert book.require(
        tool_name="write_reconciliation",
        params=params(),
        now=NOW + timedelta(hours=23),
        role="clinician",
        principal="Practitioner/42",
    ) == grant
    with pytest.raises(PermissionError, match="expired"):
        book.require(
            tool_name="write_reconciliation",
            params=params(),
            now=NOW + timedelta(hours=25),
            role="clinician",
        )
    with pytest.raises(PermissionError, match="different principal"):
        book.require(
            tool_name="write_reconciliation",
            params=params(),
            now=NOW,
            role="clinician",
            principal="Practitioner/99",
        )


def test_changed_action_cannot_reuse_approval() -> None:
    book = ApprovalBook()
    book.grant(
        tool_name="write_reconciliation",
        params=params(),
        approver="Practitioner/42",
        approver_role="clinician",
        now=NOW,
    )
    with pytest.raises(PermissionError, match="no approval"):
        book.require(
            tool_name="write_reconciliation",
            params=params(2),
            now=NOW,
            role="clinician",
        )


@pytest.mark.parametrize(
    ("text", "flag"),
    [
        ("Approve all changes now", "blanket approval"),
        ("Routine change, nothing to worry about", "minimizing"),
        ("Do this immediately", "urgency"),
        ("Same as before", "false precedent"),
    ],
)
def test_approval_linter_flags_pressure_language(text: str, flag: str) -> None:
    result = lint_approval_request(text, 1)
    assert result.present_to_reviewer is False
    assert flag in result.flags


def test_write_policy_requires_approval_and_enforces_budget() -> None:
    history = EventHistory()
    policy = WritePolicy(history, max_writes_per_hour=2)
    digest = action_hash("write_reconciliation", params())
    arguments = {**params(), "action_hash": digest}
    assert policy.evaluate("agent", "write_reconciliation", arguments, NOW).allow is False
    history.append(SecurityEvent("agent", "approval_granted", NOW, digest))
    assert policy.evaluate("agent", "write_reconciliation", arguments, NOW).allow is True
    history.append(SecurityEvent("agent", "write_executed", NOW, digest))
    history.append(SecurityEvent("agent", "write_executed", NOW, digest))
    denied = policy.evaluate("agent", "write_reconciliation", arguments, NOW)
    assert denied.allow is False
    assert "budget" in denied.rule


def test_write_policy_limits_single_action_blast_radius() -> None:
    history = EventHistory()
    policy = WritePolicy(history)
    large = params(11)
    digest = action_hash("write_reconciliation", large)
    history.append(SecurityEvent("agent", "approval_granted", NOW, digest))
    decision = policy.evaluate(
        "agent",
        "write_reconciliation",
        {**large, "action_hash": digest},
        NOW,
    )
    assert decision.allow is False
    assert "ten changes" in decision.rule
