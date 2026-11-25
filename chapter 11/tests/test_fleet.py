"""The fleet, the improvement gate, the pause rule, and retirement."""

import copy

import pytest

from chapter11.fleet import contract_breaks, listing_gaps, reconcile
from chapter11.improve import must_pause, review
from chapter11.retire import RetirementBlocked, retire
from chapter11.settings import load
from examples.retirement import systems


def test_fifteen_agents_and_four_that_cannot_be_listed():
    register = load("fleet")["register"]
    assert len(register) == 15
    assert sum(e["found"] == "sweep" for e in register) == 11
    unlistable = [e["agent"] for e in register if len(listing_gaps(e)) > 1]
    assert len(unlistable) == 4


def test_a_complete_entry_has_no_gaps():
    entry = load("fleet")["register"][0]
    assert listing_gaps(entry) == []
    assert listing_gaps({**entry, "sponsor": None}) == ["no named sponsor"]


def test_reconciliation_looks_both_ways():
    data = load("fleet")
    findings = reconcile(data["register"], data["vendors"])
    assert (
        "shift-report: we say cloud-b, and cloud-b does not list it" in findings
    )
    assert sum("nobody sponsors it" in f for f in findings) == 5
    assert sum("no registry covers" in f for f in findings) == 2
    extra = {
        **data["vendors"],
        "cloud-a": data["vendors"]["cloud-a"] + ["ghost"],
    }
    assert "ghost: in cloud-a, not in our register" in reconcile(
        data["register"], extra
    )


def test_a_contract_change_is_caught_only_for_registered_consumers():
    contract = load("fleet")["contract"]
    known = contract_breaks(contract["v3"], contract["registered_consumers"])
    assert known == {
        "maintenance-planner": ["lead_time_days"],
        "spares-forecast": [],
    }
    assert contract_breaks(contract["v2"], contract["registered_consumers"]) == {
        "maintenance-planner": [],
        "spares-forecast": [],
    }


def test_the_gate_passes_a_real_fix_and_holds_a_gamed_one():
    first, second, third = load("improvements")["proposals"]
    assert review(first) == []
    assert len(review(second)) == 2
    assert any("never write" in reason for reason in review(third))


def test_the_proposer_cannot_approve_its_own_change():
    first = load("improvements")["proposals"][0]
    assert review({**first, "approver": first["proposer"]}) == [
        "needs an approver who is not the proposer"
    ]


def test_a_fix_that_hurts_the_held_out_set_is_held():
    first = copy.deepcopy(load("improvements")["proposals"][0])
    first["after"]["held_out"] = 0.90
    assert "held_out set got worse" in review(first)


def test_the_thirty_minute_rule():
    assert must_pause(30, ruled_out=False)
    assert not must_pause(29, ruled_out=False)
    assert not must_pause(500, ruled_out=True)


def test_retirement_stops_while_a_credential_is_live():
    data = load("retirement")
    register, traces, identity, archive = systems(data)
    with pytest.raises(RetirementBlocked, match="legacy-gw-0098"):
        retire(
            data["agent"],
            data["successor"],
            data["today"],
            register,
            traces,
            identity,
            archive,
        )
    assert register.entries[data["agent"]]["status"] == "deprecated"
    assert archive.held == {}


def test_retirement_stops_while_a_caller_has_not_reached_the_successor():
    data = load("retirement")
    data["calls"] = [
        c
        for c in data["calls"]
        if c["caller"] != "shift-report" or c["agent"] == "alert-sorter"
    ]
    register, traces, identity, archive = systems(data)
    with pytest.raises(RetirementBlocked, match="shift-report"):
        retire(
            data["agent"],
            data["successor"],
            data["today"],
            register,
            traces,
            identity,
            archive,
        )
    assert data["agent"] in identity.active


def test_retirement_completes_and_finds_the_caller_nobody_listed():
    data = load("retirement")
    register, traces, identity, archive = systems(data)
    identity.revoke_at_source(data["agent"], "legacy-gw-0098")
    obituary = retire(
        data["agent"],
        data["successor"],
        data["today"],
        register,
        traces,
        identity,
        archive,
    )
    assert obituary["unlisted_callers"] == ["shift-report"]
    assert obituary["tokens_revoked"] == 3
    assert "energy-report" not in obituary["callers_moved"]
    assert register.entries[data["agent"]]["status"] == "retired"
    assert (
        archive.held[data["agent"]]["keep_until"]
        == "seven years after retirement"
    )
    assert identity.live_tokens(data["agent"]) == []


def test_the_printed_register_entries_agree_with_the_data_behind_the_examples():
    entry, parts = load("register-entry"), load("parts-availability")
    assert (
        entry["autonomy"]["ceiling"]
        == load("evidence")["ceilings"][entry["agent"]]
    )
    assert entry["autonomy"]["rung"] == load("year")["rungs"][-1][1]
    listed = {c["agent"] for c in parts["consumers"]}
    assert listed == set(load("fleet")["contract"]["registered_consumers"])
