"""The simplest agent in the chapter, run synchronously with Runner.run_sync."""

from agents import Agent, Runner

from claims_pipeline.settings import MODELS

claims_reviewer = Agent(
    name="claims_reviewer",
    model=MODELS.review,
    instructions=(
        "You are a senior insurance claims reviewer. "
        "Analyze submitted claims for completeness, "
        "flag missing documentation, and assess whether "
        "the claim falls within standard policy coverage. "
        "Always cite the specific policy section that "
        "applies to your determination."
    ),
)

CLAIM_TEXT = (
    "Claim #4821: Water damage to basement. "
    "Policy: HO-3. Date of loss: 2026-01-15. "
    "Submitted documents: photos, contractor estimate."
)


if __name__ == "__main__":
    result = Runner.run_sync(claims_reviewer, CLAIM_TEXT)
    print(result.final_output)
