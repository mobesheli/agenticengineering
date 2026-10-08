from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from chapter10.evidence import emit_deployment_evidence, verify_manifest

CHAPTER_ROOT = Path(__file__).resolve().parents[1]


def test_evidence_pack_is_complete_and_hashed(tmp_path) -> None:
    output = tmp_path / "evidence"
    summary = emit_deployment_evidence(output)
    assert summary == {
        "pipeline_passed": True,
        "listing_first_attempt": False,
        "listing_after_evidence": True,
        "agents_on_board": 4,
        "kill_switches_drilled": 6,
        "manifest_verified": True,
    }
    assert verify_manifest(output)


def test_cli_runs_the_offline_release_review(tmp_path) -> None:
    output = tmp_path / "cli-evidence"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "chapter10",
            "--output-dir",
            str(output),
        ],
        cwd=CHAPTER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["pipeline_passed"]
    assert (output / "manifest.json").is_file()


def test_cli_listing_demo_shows_both_decisions(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "chapter10",
            "--listing-demo",
            "--output-dir",
            str(tmp_path / "listing"),
        ],
        cwd=CHAPTER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert not payload["first_attempt"]["accepted"]
    assert payload["after_evidence"]["accepted"]
