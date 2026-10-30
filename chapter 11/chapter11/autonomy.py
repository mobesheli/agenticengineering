"""A ceiling, measured promotion evidence, and automatic downward rules."""

from __future__ import annotations

from .artifacts import digest, load_json
from .models import AgentEntry, Approval, PromotionEvidence, PromotionRule


def load_rules() -> dict[int, PromotionRule]:
    return {
        r["target"]: PromotionRule.model_validate(r) for r in load_json("ladder.json")
    }


def pass_hat_k(trials: list[list[bool]], k: int) -> float:
    """Empirical share of cases passing all k trials; never average per-attempt rates."""
    if not trials or any(len(row) != k for row in trials):
        raise ValueError(f"every case needs exactly {k} trials")
    if any(type(value) is not bool for row in trials for value in row):
        raise ValueError("trial results must be booleans")
    return sum(all(row) for row in trials) / len(trials)


def promotion_gaps(
    entry: AgentEntry,
    evidence: PromotionEvidence,
    rule: PromotionRule,
    target_rung: int,
    *,
    day: int,
) -> list[str]:
    if target_rung > entry.ceiling:
        return ["above this agent's ceiling; only the risk owners can move it"]
    gaps = []
    if entry.status != "live" or not entry.sponsored(day):
        gaps.append("a live entry and current sponsor attestation are required")
    if entry.drift_hold_active:
        gaps.append("an active drift hold blocks promotion")
    if (entry.rung, target_rung) != (rule.source, rule.target):
        gaps.append("promotion must follow the next declared transition")
    if evidence.bundle != entry.bundle:
        gaps.append("evidence belongs to a different release bundle")
    if evidence.observed_days < rule.window_days:
        gaps.append("observation window not yet met")
    try:
        if pass_hat_k(evidence.trials, rule.k) < rule.min_pass_k:
            gaps.append("must-always-work steps are not reliable enough")
    except ValueError as exc:
        gaps.append(str(exc))
    if evidence.planted_caught / evidence.planted_total < rule.min_catch_rate:
        gaps.append("reviewers missed planted checks; approval rate is not evidence")
    if not evidence.cost_in_band:
        gaps.append("cost per successful outcome outside the tier's band")
    if evidence.days_since_incident < rule.incident_free_days:
        gaps.append("incident-free window not yet met")
    if target_rung >= 2:
        if not evidence.exception_rate_stable:
            gaps.append("exception rate is not stable")
        if (
            evidence.reviewer_miss_rate is None
            or evidence.reviewer_miss_rate > rule.max_reviewer_miss_rate
        ):
            gaps.append("automated reviewer miss rate has not cleared its threshold")
    if target_rung >= 3:
        if not evidence.review_cadence_met:
            gaps.append("sampled review cadence not met")
        if evidence.unreviewed_irreversible_actions:
            gaps.append("irreversible actions escaped approval")
        if evidence.drill_age_days is None or evidence.drill_age_days > 90:
            gaps.append("no timed kill-switch drill in the last quarter")
    if target_rung == 4 and not evidence.finance_controls:
        gaps.append("finance controls have not been evidenced")
    return gaps


def promotion_digest(
    entry: AgentEntry, evidence: PromotionEvidence, target: int
) -> str:
    return digest(
        {
            "entry": entry.model_dump(),
            "evidence": evidence.model_dump(),
            "target": target,
        }
    )


def promote(
    entry: AgentEntry,
    evidence: PromotionEvidence,
    rule: PromotionRule,
    approvals: list[Approval],
    *,
    day: int,
) -> AgentEntry:
    gaps = promotion_gaps(entry, evidence, rule, rule.target, day=day)
    expected = promotion_digest(entry, evidence, rule.target)
    signed = {a.role for a in approvals if a.subject_digest == expected}
    gaps.extend(
        f"missing bound approval: {role}"
        for role in rule.signer_roles
        if role not in signed
    )
    if not any(
        a.role == "sponsor" and a.name == entry.sponsor and a.subject_digest == expected
        for a in approvals
    ):
        gaps.append("the current sponsor must sign")
    if gaps:
        raise ValueError("; ".join(gaps))
    return entry.model_copy(update={"rung": rule.target})


def should_drop(shift: dict, rule: PromotionRule) -> bool:
    return (
        shift["consecutive_denials"] >= rule.consecutive_denials
        or shift["denials"] >= rule.shift_denials
        or shift["drift_hold_active"]
    )


def action_route(entry: AgentEntry, action: str, *, irreversible: bool = False) -> str:
    if entry.status != "live" or entry.drift_hold_active:
        return "refused"
    if entry.rung == 0:
        return "draft_only"
    if irreversible or action in entry.always_approve or entry.rung == 1:
        return "approval"
    return "automatic" if action in entry.allow_actions else "approval"
