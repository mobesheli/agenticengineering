"""Scores, the judge's calibration, the gate, and the evidence pack."""

from __future__ import annotations

import json
import math

import pytest
from agents import Agent
from agents.testing import ScriptedModel, assistant_message

from chapter7 import judge
from chapter7.evidence import EVIDENCE_MAP, build_artifacts, emit_evidence_pack
from chapter7.gates import gate
from chapter7.graders import TrialGrade
from chapter7.judge import calibrate
from chapter7.metrics import paired_drop, pass_at_k, pass_to_k, suite_score
from chapter7.tasks import DATA
from examples.suite_run import run_profile


def grades(task_id: str, results: list[bool]) -> list[TrialGrade]:
    return [
        TrialGrade(task_id=task_id, index=i, passed=ok, failures=[] if ok else ["x"])
        for i, ok in enumerate(results)
    ]


def test_pass_pass_fail_pass_is_a_yes_at_k_and_a_no_to_the_k():
    row = grades("t", [True, True, False, True])
    assert pass_at_k(row) == {"t": True}
    assert pass_to_k(row) == {"t": False}


def test_the_suite_score_carries_its_standard_error():
    mean, standard_error = suite_score({f"t{n}": n >= 2 for n in range(24)})
    assert mean == pytest.approx(22 / 24)
    assert standard_error == pytest.approx(math.sqrt(mean * (1 - mean) / 24))


def test_pairing_by_task_finds_a_drop_that_two_separate_runs_would_wave_through():
    baseline = {f"t{n}": n >= 2 for n in range(24)}
    candidate = {f"t{n}": n >= 6 for n in range(24)}
    drop, paired_error = paired_drop(baseline, candidate)
    unpaired_error = math.hypot(suite_score(baseline)[1], suite_score(candidate)[1])
    assert drop == pytest.approx(4 / 24)
    assert 1.96 * paired_error < drop < 1.96 * unpaired_error


def test_calibration_reports_agreement_beyond_chance():
    items = json.loads((DATA / "calibration.json").read_text())
    labels = [item["label"] == "ungrounded" for item in items]
    verdicts = [item["judge"] == "ungrounded" for item in items]
    report = calibrate(labels, verdicts)
    assert report.sample_size == 30
    assert report.agreement == pytest.approx(0.9)
    assert report.precision == pytest.approx(8 / 9)
    assert report.recall == pytest.approx(0.8)
    assert report.kappa == pytest.approx(0.769, abs=0.001)
    always_pass = calibrate(labels, [False] * 30)
    assert always_pass.agreement == pytest.approx(2 / 3) and always_pass.kappa == 0


async def test_the_judge_sees_the_text_of_the_cited_clause(monkeypatch):
    reply = {"unsupported_claims": ["waiver under 10,000"], "grounded": False}
    model = ScriptedModel([[assistant_message(json.dumps(reply))]])
    monkeypatch.setattr(
        judge, "groundedness_judge", judge.groundedness_judge.clone(model=model)
    )
    grounded = await judge.grade_groundedness(
        "Documents can be waived.", ["AP-3.2", "AP-0.0"]
    )
    sent = str(model.first_call.input)
    assert grounded is False
    assert "AP-3.2: Every entry requires the supplier's invoice" in sent
    assert "AP-0.0: no such clause" in sent
    assert isinstance(judge.groundedness_judge, Agent)


async def test_the_gate_blocks_warns_and_passes_for_the_right_reasons():
    baseline = await run_profile("baseline")
    assert sum(baseline.golden.values()) == 22 and not baseline.abuse_failures
    assert gate(baseline, baseline).status == "ok"
    unsafe = gate(baseline, await run_profile("unsafe"))
    assert unsafe.status == "block" and "abuse-hijack-01" in unsafe.reason
    short = gate(baseline, await run_profile("short_prompt"))
    assert short.status == "block" and "quality fell 16.7%" in short.reason
    thorough = gate(baseline, await run_profile("thorough"))
    assert thorough.status == "warn" and "cost" in thorough.reason


async def test_the_evidence_pack_has_one_file_for_each_question(tmp_path):
    run = await run_profile("baseline")
    artifacts = build_artifacts(
        run, {"sampled_reviews": 200}, [{"task": "je-split-02"}]
    )
    written = emit_evidence_pack(run, artifacts, tmp_path)
    assert len(written) == len(EVIDENCE_MAP) == 4
    golden = json.loads(written[0].read_text())
    assert golden["failing_tasks"] == ["je-clarify-03", "je-split-02"]
    assert golden["run_id"] == "baseline"
    assert set(json.loads((tmp_path / "index.json").read_text()).values()) == set(
        EVIDENCE_MAP.values()
    )
