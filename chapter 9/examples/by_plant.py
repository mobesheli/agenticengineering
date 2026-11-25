"""Cost per approved work order by plant, as it looks and by like for like.

python -m examples.by_plant
"""

from chapter9.month import load_month
from chapter9.pricecard import load_price_card
from chapter9.report import cost_per_outcome
from examples.common import baseline


def table(rows: list[dict], keys: tuple[str, ...]) -> None:
    for row in rows:
        name = "  ".join(f"{row[key]:<9}" for key in keys)
        low, high = row["rate_low"], row["rate_high"]
        cost, base = row["usd_per_approved"], row["baseline_usd"]
        print(
            f"  {name:<20}{row['attempts']:>6,}{row['rate']:>6.0%}"
            f"  {low:.0%} to {high:.0%}{cost:>8.2f}{base:>8.2f}  {row['verdict']}"
        )


def main() -> None:
    card, human = load_price_card(), baseline()
    for name in ("before", "after"):
        month, runs = load_month(name, card)
        print(f"{month['label']}")
        print("  by plant           tries  rate  95% interval   cost    base")
        table(cost_per_outcome(runs, card, human, by=("plant",)), ("plant",))
        print("  by plant and severity")
        table(cost_per_outcome(runs, card, human), ("plant", "severity"))
        print()


if __name__ == "__main__":
    main()
