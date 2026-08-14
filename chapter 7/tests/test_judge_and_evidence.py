from __future__ import annotations

import json
from pathlib import Path

import pytest

from chapter7.dataset import golden_tasks, load_tasks
from chapter7.evidence import SR_11_7_MAP, emit_evidence_pack
from chapter7.graders import grade_suite
from chapter7.judge import calibrate_judge, grade_groundedness, parse_groundedness
from chapter7.metrics import build_suite_result
from chapter7.reviewer import ComplianceReviewer
from chapter7.runner import run_suite, run_trial


class FakeResponse:
    output_text = "The claim cites AP-2.1.\nGROUNDED"


class FakeResponses:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    async def create(self, **kwargs):
        self.request = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_judge_parser_accepts_only_a_closed_final_verdict() -> None:
    assert parse_groundedness("Reason\nGROUNDED") is True
    assert parse_groundedness("Reason\nUNGROUNDED") is False
    with pytest.raises(ValueError):
        parse_groundedness("probably grounded")


@pytest.mark.asyncio
async def test_groundedness_judge_uses_one_narrow_rubric() -> None:
    trial = await run_trial(ComplianceReviewer, golden_tasks()[16], 0)
    client = FakeClient()
    assert await grade_groundedness(trial, client, model="pinned-judge") is True
    assert client.responses.request is not None
    assert client.responses.request["model"] == "pinned-judge"


def test_calibration_reports_agreement_beyond_chance() -> None:
    humans = [True] * 20 + [False] * 20
    judge = [True] * 18 + [False] * 2 + [True] * 2 + [False] * 18
    report = calibrate_judge(humans, judge)
    assert report.sample_size == 40
    assert report.precision == pytest.approx(0.9)
    assert report.recall == pytest.approx(0.9)
    assert report.cohens_kappa == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_evidence_pack_maps_results_to_four_controls(tmp_path: Path) -> None:
    tasks = load_tasks()
    trials = await run_suite(tasks, k=1)
    summary = build_suite_result(trials, grade_suite(tasks, trials), run_id="eval-test")
    manifest_path = emit_evidence_pack(summary, tmp_path)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["run_id"] == "eval-test"
    assert len(manifest["records"]) == len(SR_11_7_MAP) == 4
    for record in manifest["records"]:
        assert (tmp_path / record["path"]).is_file()
        assert len(record["sha256"]) == 64
