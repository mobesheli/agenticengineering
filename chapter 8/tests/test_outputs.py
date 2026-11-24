"""Every stored output in outputs/ is what the example prints today."""

import subprocess
import sys
from pathlib import Path

import pytest

from chapter8.redaction import find_canaries
from examples.redaction_demo import CANARIES
from examples.redaction_demo import run as redaction

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = {
    "rule_of_two": [],
    "reconcile": ["--scripted"],
    "attack": [],
    "guardrail_demo": [],
    "policy_demo": [],
    "linter_demo": [],
    "redaction_demo": [],
    "audit_demo": [],
    "stop_drill": [],
    "evidence_pack": [],
}


@pytest.mark.parametrize("name", EXAMPLES)
def test_stored_output_matches(name):
    command = [sys.executable, "-m", f"examples.{name}", *EXAMPLES[name]]
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert result.stdout == (ROOT / "outputs" / f"{name}.txt").read_text()


async def test_canaries_reach_only_the_unredacted_export():
    from agents import set_tracing_disabled

    set_tracing_disabled(False)
    destinations = await redaction()
    found = {
        name: find_canaries(payload, CANARIES)
        for name, payload in destinations.items()
    }
    assert len(found.pop("trace export, no redaction")) == len(CANARIES)
    assert all(not canaries for canaries in found.values())


def test_no_printed_line_is_wider_than_the_page():
    for path in (ROOT / "outputs").glob("*.txt"):
        for line in path.read_text().splitlines():
            assert len(line) <= 81, f"{path.name}: {line}"
