"""The claims reviewer returning a typed ClaimVerdict instead of prose."""

from agents import Agent, Runner

from claims_pipeline.agents import REVIEW_INSTRUCTIONS
from claims_pipeline.models import ClaimVerdict
from claims_pipeline.settings import MODELS
from examples.first_agent import CLAIM_TEXT

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=REVIEW_INSTRUCTIONS,
    output_type=ClaimVerdict,
)

if __name__ == "__main__":
    result = Runner.run_sync(claims_reviewer, CLAIM_TEXT)
    verdict = result.final_output
    print(type(verdict).__name__)
    print(verdict.model_dump_json(indent=2))
