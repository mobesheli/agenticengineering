import asyncio
from types import SimpleNamespace

from chapter11.live import build_consolidator, sdk_merger
from chapter11.memory import MemoryStore, Merged


def test_agent_uses_declared_output_and_explicit_model():
    agent = build_consolidator("fixture-model")
    assert agent.output_type is Merged
    assert agent.model == "fixture-model"
    assert agent.tools == []


def test_sdk_output_and_disabled_tracing_without_a_network_call(monkeypatch):
    from agents import Runner

    store = MemoryStore.from_fixture()
    group = [store.records["pump-new-a"], store.records["pump-new-b"]]
    merged = Merged(
        fact=group[0].fact,
        source_ids=["asset-change-2", "inspection-180"],
        confidence=1,
    )
    seen = {}

    async def run(agent, payload, **kwargs):
        seen.update(kwargs)
        assert "pump-new-a" in payload
        return SimpleNamespace(final_output=merged)

    monkeypatch.setattr(Runner, "run", run)
    assert asyncio.run(sdk_merger("fixture-model")(group)) == merged
    assert seen["max_turns"] == 2
    assert seen["run_config"].tracing_disabled
