import asyncio

import pytest

from chapter11.artifacts import load_json
from chapter11.memory import MemoryStore, Merged, hygiene_pass, offline_merge, score


def run(store, **kwargs):
    return asyncio.run(
        hygiene_pass(
            store,
            load_json("asset-register.json"),
            load_json("memory-probes.json"),
            day=180,
            **kwargs,
        )
    )


def test_hygiene_order_sources_and_forgetting():
    store = MemoryStore.from_fixture()
    report = run(store)
    assert report["stages"] == ["expire", "supersede", "consolidate", "verify"]
    assert report["before"] == {"recall": 1, "forgetting": 0}
    assert report["effective_after"] == {"recall": 1, "forgetting": 1}
    assert not report["rolled_back"]
    assert store.records["orphan"].status == "quarantined"
    assert store.records["expired-note"].status == "expired"
    summary = next(m for m in store.active() if m.subject == "plant3-pump")
    assert set(summary.source_ids) == {"asset-change-2", "inspection-180"}
    assert summary.expires_day == 365


def test_erasure_reaches_every_tier_and_survives_snapshot_restore():
    store = MemoryStore.from_fixture()
    snapshot = store.snapshot()
    removed = store.erase("employee-event")["removed"]
    assert len(removed) == 5
    assert {
        "employee-fact",
        "employee-summary",
        "employee-embedding",
        "employee-archive",
        "employee-backup",
    } == set(removed)
    store.restore(snapshot)
    assert not any(m.subject == "employee-17" for m in store.records.values())
    assert store.erase("employee-event")["removed"] == []


def test_quarantine_follows_transitive_lineage():
    store = MemoryStore.from_fixture()
    assert set(store.quarantine("contractor-email")) == {
        "lockout-email",
        "lockout-summary",
        "lockout-derived",
    }
    assert not any(m.subject == "plant2-lockout" for m in store.active())


def test_regression_in_either_score_rolls_back():
    store = MemoryStore.from_fixture()
    original = {k: m.model_dump() for k, m in store.records.items()}
    calls = 0

    def regressing_scorer(store, probes):
        nonlocal calls
        calls += 1
        return (
            {"recall": 0.5, "forgetting": 1}
            if calls == 2
            else {"recall": 1, "forgetting": 0}
        )

    report = run(store, scorer=regressing_scorer)
    assert report["rolled_back"]
    assert {k: m.model_dump() for k, m in store.records.items()} == original
    assert store.last_run is None


def test_provider_failure_restores_snapshot():
    store = MemoryStore.from_fixture()
    original = {k: m.model_dump() for k, m in store.records.items()}

    async def failure(group):
        raise RuntimeError("simulated model failure")

    with pytest.raises(RuntimeError):
        run(store, merge=failure)
    assert {k: m.model_dump() for k, m in store.records.items()} == original


def test_fabricated_sources_cannot_replace_memory():
    store = MemoryStore.from_fixture()

    async def fabricate(group):
        return Merged(fact=group[0].fact, source_ids=["invented-event"], confidence=1)

    report = run(store, merge=fabricate)
    assert report["rolled_back"]  # Removing the only supported fact fails recall.
    assert not any("invented-event" in m.source_ids for m in store.records.values())


def test_offline_merge_refuses_cross_subjects():
    store = MemoryStore.from_fixture()
    with pytest.raises(ValueError, match="one subject"):
        asyncio.run(
            offline_merge([store.records["pump-new-a"], store.records["employee-fact"]])
        )


def test_repeated_hygiene_does_not_duplicate_active_facts():
    store = MemoryStore.from_fixture()
    run(store)
    run(store)
    assert len([m for m in store.active() if m.subject == "plant3-pump"]) == 1
    assert score(store, load_json("memory-probes.json"))["forgetting"] == 1
