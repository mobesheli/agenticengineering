import asyncio
import json
import subprocess
import sys

import pytest

from chapter11.artifacts import CHAPTER_ROOT, verify_manifest
from chapter11.board import replay, replay_year, write_board
from chapter11.evidence import emit_evidence
from chapter11.retirement import RetirementLab


def test_retirement_stops_before_archive_when_a_token_survives(tmp_path):
    lab = RetirementLab.from_fixture()
    with pytest.raises(RuntimeError, match="credential residue"):
        lab.retire(
            day=340,
            signed_by="Casey Patel",
            output_dir=tmp_path,
            stubborn_tokens=("token-b",),
        )
    assert lab.state["entry"]["status"] == "deprecated"
    assert not lab.state["identity_active"]
    assert not (tmp_path / "archive").exists()
    assert lab.state["memory"]
    obituary = lab.retire(day=340, signed_by="Casey Patel", output_dir=tmp_path)
    assert lab.state["entry"]["status"] == "retired"
    assert set(obituary["callers"]) == {"plant3-console", "unlisted-night-job"}
    assert "obsolete-client" not in obituary["callers"]
    assert all(not t["active"] for t in lab.state["tokens"])
    assert lab.state["memory"] == []
    assert verify_manifest(tmp_path / "archive")
    assert lab.steps.index("archive") < lab.steps.index("delete_active_memory")
    assert lab.retire(day=340, signed_by="Casey Patel", output_dir=tmp_path) == obituary


def test_unsigned_or_unqualified_retirement_cannot_freeze(tmp_path):
    lab = RetirementLab.from_fixture()
    with pytest.raises(ValueError, match="sponsor"):
        lab.retire(day=340, signed_by="optimizer", output_dir=tmp_path)
    lab.state["successor"]["suite"] = "unrelated-suite"
    with pytest.raises(ValueError, match="same-suite"):
        lab.retire(day=340, signed_by="Casey Patel", output_dir=tmp_path)
    assert lab.state["entry"]["status"] == "live"


@pytest.mark.parametrize(
    "day,rung",
    [
        (0, 1),
        (97, 0),
        (98, 0),
        (99, 1),
        (140, 1),
        (170, 2),
        (269, 2),
        (270, 3),
        (365, 3),
    ],
)
def test_replay_runs_the_control_rules(day, rung):
    state = replay(day)
    assert state["entry"]["rung"] == rung
    assert all(e["day"] <= day for e in state["events"])
    assert state["entry"]["ceiling"] == 3


def test_replay_attestation_and_refusals():
    assert not replay(330)["sponsored"]
    assert replay(365)["entry"]["sponsor"] == "Taylor Brooks"
    assert replay(365)["sponsored"]
    assert replay(2)["events"][-1]["decision"] == "hold"
    assert replay(2)["effective_configuration"]["reasoning_effort"] == "high"
    assert replay(2)["pinned_configuration"]["reasoning_effort"] == "medium"
    assert replay(140)["events"][-1]["decision"] == "refused"
    frames = replay_year()
    assert len(frames) == 366
    assert all(f["entry"]["rung"] <= f["entry"]["ceiling"] for f in frames)
    assert replay(365) == replay(365)
    with pytest.raises(ValueError):
        replay(366)


def test_evidence_manifest_detects_tamper_addition_and_deletion(tmp_path):
    summary = asyncio.run(emit_evidence(tmp_path, day=97))
    assert summary["manifest_verified"] and summary["rung"] == 0
    assert (tmp_path / "board.html").exists()
    assert verify_manifest(tmp_path)
    extra = tmp_path / "extra.txt"
    extra.write_text("unexpected")
    assert not verify_manifest(tmp_path)
    extra.unlink()
    assert verify_manifest(tmp_path)
    path = tmp_path / "board-state.json"
    original = path.read_text()
    path.write_text("{}")
    assert not verify_manifest(tmp_path)
    path.write_text(original)
    assert verify_manifest(tmp_path)
    path.unlink()
    assert not verify_manifest(tmp_path)


def test_nonempty_output_preserves_existing_files(tmp_path):
    path = tmp_path / "keep.txt"
    path.write_text("existing evidence")
    with pytest.raises(ValueError, match="empty output"):
        asyncio.run(emit_evidence(tmp_path))
    assert path.read_text() == "existing evidence"


def test_board_escapes_embedded_script_content(tmp_path):
    frames = [replay(0)]
    frames[0]["entry"]["sponsor"] = "</script><script>alert(1)</script>"
    path = tmp_path / "board.html"
    write_board(path, frames)
    assert "</script><script>alert" not in path.read_text()
    assert "\\u003c/script>" in path.read_text()


def test_cli_replay_and_invalid_day():
    result = subprocess.run(
        [sys.executable, "-m", "chapter11", "--day", "97", "--replay-only"],
        cwd=CHAPTER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["entry"]["rung"] == 0
    bad = subprocess.run(
        [sys.executable, "-m", "chapter11", "--day", "366"],
        cwd=CHAPTER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0


def test_live_mode_requires_explicit_settings():
    result = subprocess.run(
        [sys.executable, "-m", "chapter11", "--live-memory"],
        cwd=CHAPTER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "requires --model" in result.stderr
