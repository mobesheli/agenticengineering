"""A narrow groundedness judge plus human-label calibration metrics."""

from __future__ import annotations

from typing import Any, Protocol

from .models import CalibrationReport, Trial
from .models_registry import MODELS

GROUNDEDNESS_RUBRIC = """You grade one criterion only: is the review rationale
grounded in the policy clauses it cites? Grounded means every factual claim
about policy is supported by a quoted or referenced clause. Explain briefly,
then answer on the final line with exactly GROUNDED or UNGROUNDED."""


class ResponsesAPI(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class JudgeClient(Protocol):
    responses: ResponsesAPI


def parse_groundedness(output_text: str) -> bool:
    lines = [line.strip() for line in output_text.splitlines() if line.strip()]
    if not lines or lines[-1] not in {"GROUNDED", "UNGROUNDED"}:
        raise ValueError("judge must end with GROUNDED or UNGROUNDED")
    return lines[-1] == "GROUNDED"


async def grade_groundedness(
    trial: Trial,
    client: JudgeClient,
    *,
    model: str = MODELS.judge,
    rubric: str = GROUNDEDNESS_RUBRIC,
) -> bool:
    response = await client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": rubric},
            {
                "role": "user",
                "content": trial.transcript.rationale_with_citations(),
            },
        ],
    )
    return parse_groundedness(response.output_text)


def calibrate_judge(
    human_labels: list[bool], judge_labels: list[bool]
) -> CalibrationReport:
    if not human_labels or len(human_labels) != len(judge_labels):
        raise ValueError("human and judge labels must be nonempty and aligned")
    true_positive = sum(human and judge for human, judge in zip(human_labels, judge_labels))
    false_positive = sum(not human and judge for human, judge in zip(human_labels, judge_labels))
    false_negative = sum(human and not judge for human, judge in zip(human_labels, judge_labels))
    matches = sum(human == judge for human, judge in zip(human_labels, judge_labels))
    sample_size = len(human_labels)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    agreement = matches / sample_size
    human_positive = sum(human_labels) / sample_size
    judge_positive = sum(judge_labels) / sample_size
    expected = human_positive * judge_positive + (1 - human_positive) * (1 - judge_positive)
    kappa = (agreement - expected) / (1 - expected) if expected < 1 else 1.0
    return CalibrationReport(
        sample_size=sample_size,
        precision=precision,
        recall=recall,
        agreement=agreement,
        cohens_kappa=kappa,
    )
