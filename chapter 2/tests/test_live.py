"""Live checks against the real API. Skipped unless OPENAI_API_KEY is set."""

import os

import pytest

from claims_pipeline.data import SAMPLE_CLAIMS
from claims_pipeline.pipeline import process_claim

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY is not set"
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("claim_id", "expected_status"),
    [("CLM-4821", "processed"), ("CLM-4822", "incomplete"), ("CLM-4823", "escalated")],
)
async def test_sample_claims_reach_the_expected_stage(claim_id, expected_status):
    outcome = await process_claim(SAMPLE_CLAIMS[claim_id])
    assert outcome.status == expected_status
