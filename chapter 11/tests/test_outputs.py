"""Every stored output in outputs/ is what the example prints today."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = [
    "drift_view",
    "promotion",
    "mandate_demo",
    "hygiene",
    "lineage_demo",
    "fleet_demo",
    "improvement",
    "retirement",
    "year_board",
]


@pytest.mark.parametrize("name", EXAMPLES)
def test_stored_output_matches(name):
    command = [sys.executable, "-m", f"examples.{name}"]
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert result.stdout == (ROOT / "outputs" / f"{name}.txt").read_text()


def test_no_printed_line_is_wider_than_the_page():
    for path in (ROOT / "outputs").glob("*.txt"):
        for line in path.read_text().splitlines():
            assert len(line) <= 81, (path.name, line)


def test_no_line_of_the_printed_code_is_wider_than_the_page():
    for path in (ROOT / "chapter11").glob("*.py"):
        for line in path.read_text().splitlines():
            assert len(line) <= 81, (path.name, line)
