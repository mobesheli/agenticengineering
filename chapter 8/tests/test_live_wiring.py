from __future__ import annotations

import pytest

from chapter8.identity import clinician_read_session
from chapter8.live import build_read_agent, run_live_read
from chapter8.reconciliation import SyntheticRecordStore, load_fixture


def test_live_read_agent_has_only_guarded_read_tools() -> None:
    store = SyntheticRecordStore([load_fixture("clean")])
    agent = build_read_agent(store)
    assert [tool.name for tool in agent.tools] == [
        "read_medications",
        "read_fills",
        "check_interactions",
    ]
    assert "write_reconciliation" not in {tool.name for tool in agent.tools}
    assert all(len(tool.tool_input_guardrails) == 1 for tool in agent.tools)


@pytest.mark.asyncio
async def test_live_route_requires_callers_environment_credential(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    patient = load_fixture("clean")
    store = SyntheticRecordStore([patient])
    session = clinician_read_session(
        clinician_ref="Practitioner/42",
        patient_id=patient.patient_id,
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await run_live_read(store, session)
