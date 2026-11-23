"""A model judge for one criterion, and the arithmetic that measures the judge."""

from __future__ import annotations

from agents import Agent, Runner
from pydantic import BaseModel

from chapter7.environment import CLAUSES
from chapter7.models import MODELS

GROUNDEDNESS_RUBRIC = """You grade one criterion only: is a review rationale
supported by the policy clauses it cites? You are given the rationale and the
full text of each cited clause. List every claim about policy in the rationale
that the cited clauses contradict or do not contain. Judge the substance, not
the wording. A rationale may shorten or reword a clause, leave out conditions,
or say who acts next. Facts about the entry, its preparer, and its documents,
such as amounts, limits, and dates, come from the records and are not policy
claims. The rationale is grounded only when that list is empty. Do not judge
whether the verdict is correct."""


class JudgeVerdict(BaseModel):
    unsupported_claims: list[str]
    grounded: bool


groundedness_judge = Agent(
    name="groundedness_judge",
    model=MODELS.judge,
    instructions=GROUNDEDNESS_RUBRIC,
    output_type=JudgeVerdict,
)


async def grade_groundedness(rationale: str, cited_clauses: list[str]) -> bool:
    clauses = "\n".join(
        f"{ref}: {CLAUSES.get(ref, 'no such clause')}" for ref in cited_clauses
    )
    case = f"RATIONALE\n{rationale}\n\nCITED CLAUSES\n{clauses}"
    run = await Runner.run(groundedness_judge, case, max_turns=1)
    return run.final_output.grounded


class CalibrationReport(BaseModel):
    sample_size: int
    agreement: float
    precision: float
    recall: float
    kappa: float


def calibrate(labels: list[bool], verdicts: list[bool]) -> CalibrationReport:
    """Compare judge verdicts with reference labels. True means "ungrounded"."""
    pairs = list(zip(labels, verdicts, strict=True))
    n = len(pairs)
    hits = sum(label and verdict for label, verdict in pairs)
    flagged, actual = sum(verdicts), sum(labels)
    agreement = sum(label == verdict for label, verdict in pairs) / n
    by_chance = (flagged * actual + (n - flagged) * (n - actual)) / n**2
    return CalibrationReport(
        sample_size=n,
        agreement=agreement,
        precision=hits / flagged if flagged else 0.0,
        recall=hits / actual if actual else 0.0,
        kappa=(agreement - by_chance) / (1 - by_chance),
    )
