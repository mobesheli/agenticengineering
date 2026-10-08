"""Adapter for bringing an existing evaluation suite onto the common gate."""

from __future__ import annotations

from typing import Any

from .models import EvaluationReport


def adapt_legacy_report(
    payload: dict[str, Any],
    *,
    bundle: str,
    floor: float,
) -> EvaluationReport:
    """Translate common legacy fields without replacing the team's evaluator."""

    passed = int(payload.get("successes", payload.get("passed", 0)))
    total = int(payload.get("cases", payload.get("total", 0)))
    suite = str(payload.get("suite_version", payload.get("suite", "legacy@unknown")))
    tokens = int(payload.get("tokens", payload.get("token_count", 0)))
    trials = int(payload.get("trials_per_case", 1))
    required_passed = int(payload.get("required_case_trials_passed", trials))
    return EvaluationReport(
        suite=suite,
        bundle=bundle,
        passed=passed,
        total=total,
        floor=floor,
        trials_per_case=trials,
        required_case_trials_passed=required_passed,
        cache_enabled=bool(payload.get("cache_enabled", False)),
        tokens=tokens,
    )
