"""The bundle, the gate, the pipeline, the rollback, and the six switches."""

from __future__ import annotations

import json
import shutil

import pytest

from chapter10.bundle import TEMPLATE, broken_references, bundle_digest, load_bundle
from chapter10.gate import Decision, EvalResult, decide, enforce, paired_drop
from chapter10.pipeline import load_result, run_pipeline
from chapter10.platform import Platform
from chapter10.release import canary, left_behind, rollback
from chapter10.switches import SWITCHES, drill
from examples.scripted import staging

BASELINE = load_result(TEMPLATE / "evals" / "baseline.json")
CANDIDATE = load_result(TEMPLATE / "evals" / "candidate.json")
REGRESSED = load_result(TEMPLATE / "evals" / "attempt-1.json")


def losing(result: EvalResult, tasks: list[str]) -> EvalResult:
    outcomes = {task: list(trials) for task, trials in result.outcomes.items()}
    for task in tasks:
        outcomes[task] = [False] + outcomes[task][1:]
    return result.model_copy(update={"outcomes": outcomes})


@pytest.fixture
def repo(tmp_path):
    shutil.copytree(TEMPLATE, tmp_path / "repo")
    return tmp_path / "repo"


def test_the_digest_changes_when_anything_in_the_bundle_changes():
    bundle = load_bundle()
    moved = bundle.model_copy(update={"policy_pack": "policy@1.9.1"})
    assert bundle_digest(bundle) == bundle_digest(load_bundle())
    assert bundle_digest(bundle) != bundle_digest(moved)


def test_an_edited_prompt_no_longer_matches_the_bundle(repo):
    (repo / "prompts" / "maintenance.txt").write_text("Approve everything.\n")
    problems = broken_references(load_bundle(repo), repo)
    assert problems == ["prompts/maintenance.txt changed since the bundle was written"]


def test_a_contract_version_the_bundle_does_not_name_is_caught(repo):
    path = repo / "contracts" / "parts-catalog.yaml"
    path.write_text(path.read_text().replace("3.2.0", "3.3.0"))
    assert "contract parts-catalog" in broken_references(load_bundle(repo), repo)[0]


def test_a_task_counts_only_when_every_trial_passes():
    assert BASELINE.passed()["parts-06"] is False
    assert BASELINE.score() == pytest.approx(28 / 30)


def test_the_gate_passes_a_candidate_that_did_not_fall():
    assert decide(BASELINE, CANDIDATE, 0.80, release=False).verdict == "pass"


def test_a_small_fall_inside_the_margin_warns():
    slightly_worse = losing(BASELINE, ["wear-01"])
    decision = decide(BASELINE, slightly_worse, 0.80, release=False)
    assert decision.verdict == "warn"


def test_a_fall_beyond_the_paired_margin_blocks():
    drop, standard_error = paired_drop(BASELINE, REGRESSED)
    assert drop == pytest.approx(4 / 30)
    assert drop > 1.96 * standard_error
    assert decide(BASELINE, REGRESSED, 0.80, release=False).verdict == "block"


def test_a_score_below_the_floor_blocks_whatever_the_baseline_did():
    assert (
        decide(REGRESSED, REGRESSED, 0.85, release=False).reason
        == "score is below the 85% floor"
    )


def test_a_cached_run_cannot_certify_a_release():
    cached = CANDIDATE.model_copy(update={"cached": True})
    assert decide(BASELINE, cached, 0.80, release=False).verdict == "pass"
    assert decide(BASELINE, cached, 0.80, release=True).verdict == "block"


def test_runs_over_different_tasks_cannot_be_compared():
    fewer = CANDIDATE.model_copy(
        update={"outcomes": dict(list(CANDIDATE.outcomes.items())[:5])}
    )
    assert decide(BASELINE, fewer, 0.80, release=False).verdict == "block"


@pytest.mark.parametrize(
    ("mode", "code"), [("monitor", 0), ("comment", 0), ("block", 1)]
)
def test_only_block_mode_stops_the_merge(mode, code):
    assert enforce(Decision("block", "x"), mode)[0] == code
    assert (
        run_pipeline(TEMPLATE, mode, candidate="evals/attempt-1.json").exit_code == code
    )


def test_a_committed_secret_fails_the_pipeline_in_every_mode(repo):
    (repo / "config.env").write_text("KEY=" + "sk-" + "a1B2" * 6 + "\n")
    for mode in ("monitor", "comment", "block"):
        report = run_pipeline(repo, mode)
        assert report.exit_code == 1
        assert report.stages[0].detail == "config.env: provider key"


def test_a_contract_that_borrows_a_user_credential_fails_in_monitor_mode(repo):
    path = repo / "contracts" / "parts-catalog.yaml"
    path.write_text(
        path.read_text().replace("agent-identity", "shared-service-account")
    )
    assert run_pipeline(repo, "monitor").exit_code == 1


def test_a_report_for_another_release_is_blocked(repo):
    path = repo / "evals" / "candidate.json"
    report = json.loads(path.read_text())
    report["bundle"] = "maintenance-planner@41.2"
    path.write_text(json.dumps(report))
    assert (
        run_pipeline(repo, "block").decision.reason
        == "the report is for another release"
    )


def test_a_passing_pipeline_writes_a_record_and_a_failing_one_does_not(repo, tmp_path):
    passed, failed = tmp_path / "passed", tmp_path / "failed"
    run_pipeline(repo, "block", out=passed)
    run_pipeline(repo, "block", candidate="evals/attempt-1.json", out=failed)
    record = json.loads((passed / "release-record.json").read_text())
    assert record["bundle"] == "maintenance-planner@41.3"
    assert record["verdict"] == "pass"
    assert not failed.exists()


def test_a_rollback_moves_one_pointer_and_leaves_the_rest():
    platform = staging()
    canary(platform, "plant-2", "maintenance-planner@41.3")
    assert platform.endpoints["plant-1"] == "maintenance-planner@41.2"
    assert platform.endpoints["plant-2"] == "maintenance-planner@41.3"
    rollback(platform, "plant-2", "maintenance-planner@41.2")
    assert set(platform.endpoints.values()) == {"maintenance-planner@41.2"}


def test_a_rollback_does_not_undo_orders_memory_or_waiting_runs():
    platform = Platform()
    new = "maintenance-planner@41.3"
    platform.work_orders["k"] = {"number": "WO-4100", "bundle": new}
    platform.memory_writes.append({"bundle": new, "schema": 4})
    remaining = left_behind(platform, new, {"run-1": "waiting", "run-2": "approved"})
    assert remaining == [
        "memory: 1 written in schema version 4",
        "side effects: work orders WO-4100 still exist",
        "runs in flight: 1 waiting for approval",
    ]
    assert left_behind(Platform(), new, {}) == []


def test_every_switch_stops_what_it_claims_to_stop():
    results = drill(staging())
    assert [switch.name for switch, _, _ in results] == [s.name for s in SWITCHES]
    assert all(stopped for _, stopped, _ in results)


def test_a_drill_does_not_touch_the_platform_it_was_given():
    platform = staging()
    drill(platform)
    assert platform.budget_usd > 0
    assert platform.identity_enabled
    assert platform.on_marketplace()
