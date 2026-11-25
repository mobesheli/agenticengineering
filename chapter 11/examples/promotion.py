"""Two promotion cases for one agent, a ceiling, and an automatic drop.

python -m examples.promotion
"""

from chapter11.autonomy import RUNGS, promotion_gaps, should_drop
from chapter11.settings import AGENT, load


def show(title: str, gaps: list[str], signers: list[str]) -> None:
    print(title)
    for gap in gaps:
        print(f"  gap: {gap}")
    if not gaps:
        print(f"  no gaps: goes to {' and '.join(signers)} to sign")


def main() -> None:
    ladder, data = load("ladder"), load("evidence")
    rule, ceiling = ladder["rung_1_to_2"], data["ceilings"][AGENT]
    first = data["day_140"]
    planted = first["planted_checks"]
    print(
        f"day 140: planners approved {first['approval_rate_last_90_days']:.0%}"
        f" of drafts, and caught {planted['caught']} of {planted['planted']}"
        " planted errors"
    )
    gaps = promotion_gaps(first["evidence"], rule, 2, ceiling)
    show(f"  {AGENT}: rung 1 to rung 2 ({RUNGS[2]})", gaps, rule["signers"])
    later = data["day_175"]
    planted, clean = later["planted_checks"], later["clean_controls"]
    print(
        f"\nday 175: caught {planted['caught']} of {planted['planted']} planted"
        f" errors, wrongly rejected {clean['wrongly_rejected']} of"
        f" {clean['shown']} clean drafts"
    )
    gaps = promotion_gaps(later["evidence"], rule, 2, ceiling)
    show(f"  {AGENT}: rung 1 to rung 2 ({RUNGS[2]})", gaps, rule["signers"])
    print("\na case nobody should bring")
    gaps = promotion_gaps(later["evidence"], rule, 4, ceiling)
    show(f"  {AGENT}: to rung 4 ({RUNGS[4]})", gaps, [])
    perfect = data["credit_decision_perfect"]["evidence"]
    gaps = promotion_gaps(perfect, rule, 2, data["ceilings"]["credit-decision"])
    show("  credit-decision: to rung 2, with perfect evidence", gaps, [])
    fired = should_drop(data["day_97_shift"], rule)
    print("\nday 97, morning shift at plant 2: the drop rule fired")
    for reason in fired:
        print(f"  {reason}")
    print(f"  {AGENT}: rung 1 to rung 0 ({RUNGS[0]}), no signature needed")


if __name__ == "__main__":
    main()
