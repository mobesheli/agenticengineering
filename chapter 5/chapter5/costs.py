"""The cost arithmetic from the chapter, as code you can rerun when prices change.

Prices are US dollars per million tokens, standard tier, as published by the
provider on the date below. They are keyed by registry role, so this module
names no model.
"""

from __future__ import annotations

from decimal import Decimal

PRICES_AS_OF = "2026-11-20"
PRICE_PER_MILLION = {
    "small": (Decimal("0.10"), Decimal("0.50")),
    "mid": (Decimal("1.00"), Decimal("5.00")),
    "frontier": (Decimal("2.00"), Decimal("10.00")),
    "frontier_canary": (Decimal("8.00"), Decimal("40.00")),
}
MILLION = Decimal(1_000_000)


def cost_per_call(role: str, tokens_in: int, tokens_out: int) -> Decimal:
    price_in, price_out = PRICE_PER_MILLION[role]
    return (tokens_in * price_in + tokens_out * price_out) / MILLION


def triage_report(alerts_per_day: int = 10_000) -> list[str]:
    triage = {role: cost_per_call(role, 3_000, 300) for role in ("small", "frontier")}
    investigation = cost_per_call("frontier", 40_000, 4_000)
    lines = [f"Prices as of {PRICES_AS_OF}. {alerts_per_day:,} alerts a day."]
    for role, each in triage.items():
        daily = each * alerts_per_day
        lines.append(
            f"Triage on the {role} tier: ${each:.5f} an alert, "
            f"${daily:,.2f} a day, ${daily * 365:,.0f} a year"
        )
    ratio = triage["frontier"] / triage["small"]
    lines.append(
        f"The frontier tier costs {ratio:.0f} times as much for the same step."
    )
    lines.append(f"One investigation on the frontier tier: ${investigation:.2f}")
    one_point = investigation * alerts_per_day / 100 * 365
    lines.append(
        f"Each extra percentage point of alerts investigated: ${one_point:,.0f} a year"
    )
    return lines
