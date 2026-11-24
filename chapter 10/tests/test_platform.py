"""The register, the listing check, the gap sheet, intake, the adapter, and the board."""

from __future__ import annotations

import json
import shutil

import pytest
import yaml

from chapter10.adapter import from_team_suite
from chapter10.board import board
from chapter10.gaps import GapSheet, blocking_gaps
from chapter10.gate import decide
from chapter10.intake import Brief, recommend
from chapter10.register import (
    DATA,
    RECORDS,
    find_unregistered,
    listing_check,
    load_entry,
    load_register,
    required_evidence,
)


@pytest.fixture
def records(tmp_path):
    shutil.copytree(RECORDS, tmp_path / "records")
    return tmp_path / "records"


def check(attempt: int, repo=RECORDS) -> list[str]:
    entry = load_entry(DATA / "candidates" / f"attempt-{attempt}.yaml")
    return listing_check(entry, required_evidence(entry.tier), repo)


def test_a_listing_is_refused_until_its_evidence_exists():
    assert check(1) == ["missing evidence: oversight_note"]
    assert check(2) == ["eval_report was produced under a different bundle"]
    assert check(3) == []


def test_a_report_edited_after_the_pipeline_ran_is_refused(records):
    path = records / "results" / "maintenance-planner" / "eval-report.json"
    path.write_text(path.read_text().replace("false", "true"))
    assert check(3, records) == ["eval_report is not the file the pipeline certified"]


def test_an_unreadable_report_refuses_the_listing(records):
    (records / "results" / "maintenance-planner" / "eval-report.json").write_text("{")
    assert check(3, records)[0].startswith("evidence cannot be read")


def test_a_record_with_a_missing_field_refuses_the_listing(records):
    (records / "results" / "maintenance-planner" / "release-record.json").write_text(
        "{}"
    )
    assert check(3, records) == ["evidence cannot be read: KeyError"]


def test_a_blocked_release_cannot_be_listed(records):
    path = records / "results" / "maintenance-planner" / "release-record.json"
    record = json.loads(path.read_text())
    path.write_text(json.dumps(record | {"verdict": "block"}))
    assert check(3, records) == ["the release gate blocked this bundle"]


def test_higher_tiers_need_more_evidence():
    assert "oversight_note" not in required_evidence("medium")
    assert "oversight_note" in required_evidence("high")
    assert set(required_evidence("low")) < set(required_evidence("medium"))


def test_agents_nobody_registered_are_found_from_the_systems_they_touch():
    inventory = yaml.safe_load((DATA / "inventory.yaml").read_text())
    register = load_register()
    assert len(find_unregistered(register[:1], inventory)) == 3
    assert find_unregistered(register, inventory) == []


def test_the_gap_sheet_passes_at_its_tier_and_blocks_a_promise_at_high_tier():
    raw = yaml.safe_load(
        (RECORDS / "gap-sheets" / "purchasing-advisor.yaml").read_text()
    )
    sheet = GapSheet.model_validate(raw)
    assert blocking_gaps(sheet) == []
    sheet.tier = "high"
    sheet.requirements["audit_records"].status = "contract"
    assert blocking_gaps(sheet) == [
        "audit_records: a contract line is not a control at this tier"
    ]
    sheet.requirements["action_limits"].status = "disqualifying"
    assert "action_limits: disqualifying for tier high" in blocking_gaps(sheet)


def test_a_risk_nobody_signed_for_blocks_the_listing():
    raw = yaml.safe_load(
        (RECORDS / "gap-sheets" / "purchasing-advisor.yaml").read_text()
    )
    sheet = GapSheet.model_validate(raw)
    sheet.requirements["usage_evidence"].accepted_by = None
    assert blocking_gaps(sheet) == [
        "usage_evidence: nobody has accepted this risk by name"
    ]


def test_intake_sends_most_ideas_somewhere_other_than_a_build():
    marketplace = yaml.safe_load((DATA / "marketplace.yaml").read_text())
    vendors = yaml.safe_load((DATA / "vendors.yaml").read_text())
    briefs = [
        Brief.model_validate(b)
        for b in yaml.safe_load((DATA / "briefs.yaml").read_text())
    ]
    routes = [recommend(brief, marketplace, vendors).route for brief in briefs]
    assert routes == ["reuse", "buy", "build"]
    scaffold = recommend(briefs[2], marketplace, vendors).scaffold
    assert scaffold["gate_mode"] == "monitor"
    assert scaffold["golden_suite"] == []


def test_the_adapter_keeps_every_attempt_so_the_gate_can_pair_by_task():
    report = json.loads((DATA / "team-suite" / "document-assistant.json").read_text())
    joined = from_team_suite(report, "document-assistant@7.0")
    assert joined.suite == "docqa@112"
    assert joined.trials == 3
    assert joined.score() == pytest.approx(36 / 40)
    assert decide(joined, joined, 0.80, release=False).verdict == "pass"


def test_the_adapter_refuses_cases_with_uneven_attempts():
    report = json.loads((DATA / "team-suite" / "document-assistant.json").read_text())
    report["cases"][0]["attempts"].pop()
    with pytest.raises(ValueError, match="same number of attempts"):
        from_team_suite(report, "document-assistant@7.0")


def test_the_board_has_one_row_for_each_agent_and_names_what_is_missing(records):
    entries = load_register()
    lines = board(entries, RECORDS)
    assert [line.split()[0] for line in lines[1:5]] == [
        entry.agent for entry in entries
    ]
    assert "allocated" in lines[-1]
    shutil.rmtree(records / "results" / "parts-quote")
    (records / "monitoring" / "parts-quote.json").unlink()
    row = board(entries, records)[3]
    assert "no report: run the gate" in row
    assert row.endswith("not configured")
