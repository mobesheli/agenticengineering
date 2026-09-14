from __future__ import annotations

from dataclasses import dataclass

import pytest

from chapter9.border import call_counterparty
from chapter9.live import build_maintenance_agent, make_live_context, run_live_case
from chapter9.maintenance import load_cases
from chapter9.replay import ActivityJournal


def test_replay_returns_recorded_effect_without_calling_the_world() -> None:
    journal = ActivityJournal()
    journal.record(
        activity_id="tool-1",
        kind="tool",
        name="write_work_order",
        request={"asset": "A-1"},
        response={"work_order": "WO-1"},
    )
    called = False

    def external_write(_):
        nonlocal called
        called = True
        return {"work_order": "WO-2"}

    assert journal.replay() == [{"work_order": "WO-1"}]
    assert called is False
    with pytest.raises(PermissionError, match="repeat external effects"):
        journal.fork("tool-1", external_write)
    assert called is False
    assert journal.fork("tool-1", external_write, allow_tool_effects=True) == [
        {"work_order": "WO-2"}
    ]
    assert called is True


@dataclass
class Reply:
    status: str
    task_id: str = "remote-42"
    server_info: dict | None = None
    metadata: dict | None = None


class Client:
    def __init__(self):
        self.calls = 0
        self.headers = []

    def send(self, task, *, headers):
        self.calls += 1
        self.headers.append(headers)
        return Reply(
            status="retry" if self.calls == 1 else "completed",
            server_info={"name": "supplier", "version": "2"},
            metadata={"cost": 0.08, "receipt_id": "receipt-9"},
        )


def test_border_span_records_retry_receipt_and_correlation_without_trusting_it() -> (
    None
):
    client = Client()
    times = iter([10.0, 10.125])
    reply, receipt = call_counterparty(
        client,
        {"part": "P-1"},
        tenant="manufacturer",
        case_id="case-9",
        clock=lambda: next(times),
    )
    assert reply.status == "completed"
    assert receipt["attempts"] == 2
    assert receipt["receipt_id"] == "receipt-9"
    assert receipt["correlation_is_authorization"] is False
    assert all(headers == {"x-correlation-id": "case-9"} for headers in client.headers)


def test_live_agent_has_only_guarded_read_tools_and_a_budgeted_model() -> None:
    context = make_live_context(load_cases()[0])
    agent = build_maintenance_agent(context)
    assert [tool.name for tool in agent.tools] == [
        "read_sensor_summary",
        "read_repair_history",
        "check_parts_catalog",
    ]
    assert all(len(tool.tool_input_guardrails) == 1 for tool in agent.tools)
    assert type(agent.model).__name__ == "BudgetedOpenAIModel"


@pytest.mark.asyncio
async def test_live_route_requires_callers_environment_credential(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await run_live_case(load_cases()[0])
