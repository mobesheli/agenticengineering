"""Every stored output is what its example prints today."""

from __future__ import annotations

from pathlib import Path

import pytest

from examples import (
    board,
    bundle_show,
    buy_route,
    contract_demo,
    intake_demo,
    listing_demo,
    pause_resume,
    pipeline_run,
    rollout_demo,
    switch_drill,
)

OUTPUTS = Path(__file__).resolve().parents[1] / "outputs"
PLAIN = [
    board,
    bundle_show,
    buy_route,
    intake_demo,
    listing_demo,
    pipeline_run,
    switch_drill,
]
ASYNC = [contract_demo, rollout_demo]


def stored(name: str) -> list[str]:
    return (OUTPUTS / f"{name}.txt").read_text().splitlines()


@pytest.mark.parametrize("example", PLAIN, ids=lambda m: m.__name__)
def test_plain_examples_match_their_stored_output(example):
    assert example.main() == stored(example.__name__.split(".")[-1])


@pytest.mark.parametrize("example", ASYNC, ids=lambda m: m.__name__)
async def test_async_examples_match_their_stored_output(example):
    assert await example.main() == stored(example.__name__.split(".")[-1])


async def test_the_scripted_pause_and_resume_matches_its_stored_output():
    assert await pause_resume.main(scripted_run=True) == stored("pause_resume_scripted")
