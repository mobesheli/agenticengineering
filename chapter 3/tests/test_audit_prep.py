"""The audit-prep agent end to end, offline, and the journal it leaves behind."""

from audit_prep import servers
from audit_prep.main import run_evidence_flow
from audit_prep.models import EvidenceRequest
from ch3.journal import Journal, ToolCallJournal


async def test_evidence_flow_publishes_once_and_journals_every_call():
    servers.evidence.bundles.clear()
    servers.evidence.published.clear()
    request = EvidenceRequest(control_id="LIQ-07", period="2026-Q3", jurisdiction="uk")
    status, journal, ctx = await run_evidence_flow(
        request, principal_id="owner@example.com", tenant_id="acme-uk", run_id="run_test_1"
    )
    assert status.status == "published" and status.artifact_count == 3
    assert servers.evidence.published == [status.bundle_id]
    rows = journal.rows("run_test_1")
    assert [row.tool_name for row in rows] == [
        "get_trial_balance_snapshot", "get_journal_entries", "get_reporting_requirements",
        "preview_evidence_bundle", "write_evidence_artifact", "write_evidence_artifact",
        "write_evidence_artifact", "publish_evidence_bundle",
    ]
    assert all(row.principal_id == "owner@example.com" for row in rows)
    assert all(row.status == "succeeded" for row in rows)
    assert rows[-1].approval_reference == "approved by reviewer"
    assert rows[-1].completed_at is not None
    assert {row.policy_version for row in rows[2:]} == {"rules-2026.07"}
    assert len({row.idempotency_key for row in rows}) == len(rows)


async def test_only_the_publish_tool_requires_approval():
    store = servers.evidence_store()
    tools = await store.list_tools()
    assert {tool.name for tool in tools} == {
        "preview_evidence_bundle", "write_evidence_artifact", "publish_evidence_bundle",
    }
    assert store._needs_approval_policy == {"publish_evidence_bundle": True}
    assert servers.data_server()._needs_approval_policy is False


def test_publish_refuses_a_bundle_whose_hash_changed_after_approval():
    store = servers.FakeEvidenceStore()
    bundle_id = store.preview_bundle(control_id="LIQ-07", period="2026-Q3")["bundle_id"]
    approved = store.write_artifact(bundle_id=bundle_id, kind="trial_balance", content="a")["bundle_hash"]
    store.write_artifact(bundle_id=bundle_id, kind="journal_sample", content="b")
    refused = store.publish(bundle_id=bundle_id, content_hash=approved)
    assert refused["ok"] is False and refused["error_class"] == "content_hash_mismatch"
    assert store.published == []


def test_journal_rows_open_pending_and_close_with_a_status():
    journal = Journal()
    row = journal.record(run_id="r", trace_id="t", tool_call_id="c1", tool_name="publish",
                         arguments={"bundle_id": "eb_1"}, principal_id="p", tenant_id="ten",
                         policy_version="v1", status="pending")
    assert row.id is not None and row.completed_at is None
    closed = journal.complete("c1", status="succeeded", result={"ok": True}, approval_reference="apr_1")
    assert closed.id == row.id and closed.completed_at is not None
    assert isinstance(closed, ToolCallJournal)
