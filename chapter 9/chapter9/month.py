"""Expand a month fixture into ledger records, one for each run."""

from __future__ import annotations

from pathlib import Path

import yaml

from chapter9.ledger import SUCCESS, ModelCall, RunRecord, ToolCall
from chapter9.meter import price_usage, usage_of
from chapter9.pricecard import PriceCard
from chapter9.settings import DATA, IDENTITY, WORKFLOW

CALLS = (
    "read_sensor_summary",
    "read_repair_history",
    "search_manual",
    "check_parts",
)
SPREAD = 7919


def load_month(name: str, card: PriceCard) -> tuple[dict, list[RunRecord]]:
    month = yaml.safe_load(Path(DATA / "months" / f"{name}.yaml").read_text())
    runs: list[RunRecord] = []
    for plant, groups in month["plants"].items():
        for severity, (attempts, approved) in groups.items():
            profile = month["severities"][severity]
            calls = [
                model_call(step, spec, card)
                for step, spec in profile["steps"].items()
            ]
            for number in range(attempts):
                place = (number * SPREAD % attempts) / attempts
                run = RunRecord(
                    f"{plant}-{severity}-{number:04d}",
                    WORKFLOW,
                    {**IDENTITY, "plant": plant, "severity": severity},
                    model_calls=list(calls),
                    tool_calls=tool_calls(profile, place),
                    turns=pick(profile["turns"], place),
                    review_minutes=profile["review_minutes"],
                )
                edited = approved + round((attempts - approved) * 0.4)
                run.outcome = (
                    SUCCESS
                    if number < approved
                    else "edited"
                    if number < edited
                    else "rejected"
                )
                run.outcome_ref = (
                    f"WO-{plant[-1]}{severity[0].upper()}{number:04d}"
                )
                runs.append(run)
    return month, runs


def model_call(step: str, spec: dict, card: PriceCard) -> ModelCall:
    usage = usage_of(
        spec["input"],
        spec["output"],
        spec["cached"],
        spec["written"],
        spec["reasoning"],
    )
    cost = price_usage(usage, card.rates(spec["model"]))
    return ModelCall(
        step,
        spec["model"],
        spec["input"],
        spec["cached"],
        spec["written"],
        spec["output"],
        spec["reasoning"],
        cost.total,
    )


def tool_calls(profile: dict, place: float) -> list[ToolCall]:
    calls = [ToolCall(name, "{}", fee_of(name), failed=False) for name in CALLS]
    calls[2] = ToolCall(CALLS[2], "{}", fee_of(CALLS[2]), failed=place >= 0.98)
    if place < profile["repeat_share"]:
        calls.append(
            ToolCall("check_parts", "{}", fee_of("check_parts"), repeat=True)
        )
    elif place < profile["repeat_share"] + profile.get("refused_share", 0.0):
        calls.append(
            ToolCall("check_parts", "{}", 0.0, repeat=True, refused=True)
        )
    return calls


def fee_of(name: str) -> float:
    return FEES[name]


def pick(spread: list[list[float]], place: float) -> int:
    edge = 0.0
    for value, share in spread:
        edge += share
        if place < edge:
            return int(value)
    return int(spread[-1][0])


FEES = yaml.safe_load((DATA / "price-card.yaml").read_text())["tools"]
