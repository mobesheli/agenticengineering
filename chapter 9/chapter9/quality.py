"""Human-calibrated production judge monitoring kept outside the agent path."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any


def cohens_kappa(human_labels: Sequence[str], judge_labels: Sequence[str]) -> float:
    """Agreement beyond chance for two equally sized label sequences."""

    if len(human_labels) != len(judge_labels) or not human_labels:
        raise ValueError("human and judge labels must be non-empty and aligned")
    count = len(human_labels)
    observed = (
        sum(human == judge for human, judge in zip(human_labels, judge_labels)) / count
    )
    human_counts = Counter(human_labels)
    judge_counts = Counter(judge_labels)
    labels = human_counts.keys() | judge_counts.keys()
    expected = sum(
        (human_counts[label] / count) * (judge_counts[label] / count)
        for label in labels
    )
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def calibration_report(
    *,
    period: str,
    judge_version: str,
    human_labels: Sequence[str],
    judge_labels: Sequence[str],
) -> dict[str, Any]:
    if len(human_labels) != len(judge_labels) or not human_labels:
        raise ValueError("human and judge labels must be non-empty and aligned")
    count = len(human_labels)
    agreement = (
        sum(human == judge for human, judge in zip(human_labels, judge_labels)) / count
    )
    confusion = Counter(zip(human_labels, judge_labels))
    return {
        "period": period,
        "judge_version": judge_version,
        "sample_size": count,
        "raw_agreement": round(agreement, 4),
        "cohens_kappa": round(cohens_kappa(human_labels, judge_labels), 4),
        "confusion": {
            f"human={human}|judge={judge}": value
            for (human, judge), value in sorted(confusion.items())
        },
        "sample_hash": hashlib.sha256(
            "\n".join(
                f"{human}|{judge}" for human, judge in zip(human_labels, judge_labels)
            ).encode()
        ).hexdigest(),
    }


@dataclass
class JudgeCalibrationMonitor:
    minimum_kappa: float = 0.55
    maximum_drop: float = 0.10
    reports: list[dict[str, Any]] = field(default_factory=list)

    def add(self, report: dict[str, Any]) -> dict[str, Any]:
        current = float(report["cohens_kappa"])
        previous = float(self.reports[-1]["cohens_kappa"]) if self.reports else current
        reasons = []
        if current < self.minimum_kappa:
            reasons.append("kappa below the calibrated operating floor")
        if previous - current > self.maximum_drop:
            reasons.append("kappa dropped beyond the monthly tolerance")
        if (
            self.reports
            and report["judge_version"] != self.reports[-1]["judge_version"]
        ):
            reasons.append("judge version changed; fresh calibration required")
        verdict = {
            **report,
            "status": "recalibrate" if reasons else "ok",
            "reasons": reasons,
        }
        self.reports.append(verdict)
        return verdict


def stable_human_review_sample(
    trace_ids: Iterable[str],
    *,
    sample_size: int,
    seed: int,
) -> list[str]:
    """Select an auditable sample outside any agent-controlled randomness."""

    population = sorted(set(trace_ids))
    if sample_size < 1 or sample_size > len(population):
        raise ValueError("sample size must fit the unique trace population")
    return sorted(random.Random(seed).sample(population, sample_size))
