"""The reviewer with its two function tools, run on a sample claim."""

from agents import Agent, Runner

from claims_pipeline.agents import REVIEW_INSTRUCTIONS
from claims_pipeline.data import SAMPLE_CLAIMS
from claims_pipeline.models import ClaimVerdict
from claims_pipeline.settings import MODELS
from claims_pipeline.tools import get_claim_history, lookup_policy

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=REVIEW_INSTRUCTIONS,
    output_type=ClaimVerdict,
    tools=[lookup_policy, get_claim_history],
)

if __name__ == "__main__":
    claim = SAMPLE_CLAIMS["CLM-4821"]
    result = Runner.run_sync(claims_reviewer, claim.as_text())
    for item in result.new_items:
        if item.type == "tool_call_item":
            print(f"tool call: {item.raw_item.name}({item.raw_item.arguments})")
    print(result.final_output.model_dump_json(indent=2))
