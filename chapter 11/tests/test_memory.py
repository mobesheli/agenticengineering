"""The hygiene pass, its checks, and lineage."""

import copy

from chapter11.lineage import erase, lineage, quarantine, restore_backup
from chapter11.memory import (
    Claim,
    Merged,
    consolidator,
    hygiene_pass,
    safe_to_merge,
    score,
)
from examples.hygiene import build
from examples.scripted import COMPRESSOR, merges


async def run_pass(reply=COMPRESSOR, ttl=None):
    store, data = build()
    agent = consolidator(merges(reply))
    result = await hygiene_pass(
        store, data["probes"], ttl or data["ttl_days"], agent
    )
    return store, result


async def test_the_pass_improves_both_scores_and_the_stale_summary_stops_winning():
    store, result = await run_pass()
    assert result["before"] == (0.7, 0.25)
    assert result["after"] == (1.0, 1.0)
    assert store.retrieve("pump-P3-feed").id == "m02"
    assert store.memories["m01"].status == "superseded"


async def test_a_memory_with_no_source_is_quarantined_and_never_merged():
    store, result = await run_pass()
    assert store.memories["m09"].status == "quarantined"
    assert store.memories["m08"].status == "active"
    assert result["quarantined"] == 1


async def test_a_merge_keeps_its_sources_and_archives_the_originals():
    store, _ = await run_pass()
    merged = store.memories["m04+m05"]
    assert merged.derived_from == ("m04", "m05")
    assert merged.source_id == "session-0090,session-0131"
    assert merged.claims == {"service_days": 60}
    assert set(store.archive) >= {"m04", "m05"}


async def test_a_merge_that_drops_a_source_is_flagged_for_a_person():
    reply = {**COMPRESSOR, "source_ids": ["session-0090"]}
    store, result = await run_pass(reply)
    assert result["merged"] == 0 and result["flagged"] == 2
    assert store.memories["m04"].status == "flagged for review"


async def test_a_merge_that_contradicts_the_asset_register_is_flagged():
    reply = {**COMPRESSOR, "claims": [{"name": "service_days", "value": "90"}]}
    _, result = await run_pass(reply)
    assert result["merged"] == 0 and result["flagged"] == 2


def test_without_a_record_the_members_must_agree_with_each_other():
    store, _ = build()
    a, b = (
        copy.deepcopy(store.memories["m04"]),
        copy.deepcopy(store.memories["m05"]),
    )
    b.claims = {"service_days": 45}
    merged = Merged(
        text="x",
        claims=[Claim(name="service_days", value="60")],
        source_ids=["session-0090", "session-0131"],
    )
    assert not safe_to_merge([a, b], merged, record={})
    assert safe_to_merge([a, b], merged, record={"service_days": 60})


async def test_a_pass_that_makes_recall_worse_restores_the_snapshot():
    store, result = await run_pass(ttl={"fact": 10, "note": 30, "summary": 365})
    assert result["restored"] is True
    assert store.memories["m03"].status == "active"
    assert store.log == ["restored the snapshot"]


def test_scores_are_shares_of_probes():
    store, data = build()
    assert score(store, data["probes"]) == (0.7, 0.25)


def test_lineage_follows_derived_memories_to_the_end():
    store, _ = build("lineage")
    assert lineage(store, {"email-7731"}) == ["m20", "m21", "m22"]
    assert quarantine(store, {"email-7731"}) == ["m20", "m21", "m22"]
    assert store.retrieve("plant-2-lockout") is None


def test_erasure_records_a_decision_for_every_copy():
    store, data = build("lineage")
    record = erase(store, set(data["erasure_sources"]), data["retain"])
    assert record["deleted"] == ["m30", "m31", "m32"]
    assert record["archive"] == ["m30", "m31"]
    assert list(record["restricted"]) == ["m33"]
    assert record["backups"] == {
        "weekly-22": ["m30", "m31", "m32"],
        "weekly-27": ["m30", "m31", "m32"],
    }
    assert not {"m30", "m31", "m32"} & store.embeddings
    assert store.retrieve("press-03-inspection") is None


def test_a_restored_backup_does_not_bring_back_what_was_erased():
    store, data = build("lineage")
    saved = store.snapshot()
    erase(store, set(data["erasure_sources"]), data["retain"])
    del store.memories["m40"]
    blocked = restore_backup(store, "weekly-22", saved)
    assert blocked == ["m30", "m31", "m32"]
    assert "m40" in store.memories and "m30" not in store.memories
    assert store.memories["m33"].status == "restricted"


def test_the_consolidator_is_shown_each_source_with_its_claims():
    from chapter11.memory import describe

    store, _ = build()
    shown = describe([store.memories["m04"], store.memories["m05"]])
    assert shown.splitlines()[0] == (
        "session-0090: Compressor C2 gets a service every 60 days."
        " [claims: service_days=60]"
    )
    assert "session-0131" in shown.splitlines()[1]
