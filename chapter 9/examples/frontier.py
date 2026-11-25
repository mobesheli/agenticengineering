"""Three configurations of the same work, compared on cost per approved order.

python -m examples.frontier
"""

from chapter9.month import load_month
from chapter9.pricecard import load_price_card
from chapter9.report import unit_cost
from examples.common import baseline


def main() -> None:
    card, human = load_price_card(), baseline()
    print(
        f"{'configuration':<28}{'model':>6}{'attempt':>9}{'approved':>10}{'per order':>11}{'baseline':>10}"
    )
    for name in ("before", "candidate", "after"):
        month, runs = load_month(name, card)
        cost = unit_cost(runs, card)
        mix = sum(human[run.identity["severity"]] for run in runs) / len(runs)
        size = f"{name}, {cost['attempts']:,} attempts"
        print(
            f"{size:<28}{cost['lines']['model tokens']:>6.2f}"
            f"{cost['per_attempt']:>9.2f}{cost['success_rate']:>10.0%}"
            f"{cost['per_approved']:>11.2f}{mix:>10.2f}"
        )
        print(f"  {month['config']}")


if __name__ == "__main__":
    main()
