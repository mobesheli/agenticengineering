"""What one approved work order costs, line by line.

python -m examples.unit_cost
"""

from chapter9.month import load_month
from chapter9.pricecard import load_price_card
from chapter9.report import cost_per_outcome, unit_cost
from examples.common import baseline


def main() -> None:
    card = load_price_card()
    month, runs = load_month("before", card)
    cost, human = unit_cost(runs, card), baseline()
    print(f"{month['label']}: {cost['attempts']:,} attempts\n")
    for name, usd in cost["lines"].items():
        print(f"  {name:<28}${usd:>6.2f}")
    print(f"  {'direct cost per attempt':<28}${cost['per_attempt']:>6.2f}")
    print(
        f"  {'approved by a planner':<28}{cost['success_rate']:>7.0%}"
        f"   ({cost['approved']:,} of {cost['attempts']:,})"
    )
    print(f"  {'cost per approved order':<28}${cost['per_approved']:>6.2f}")
    mix = sum(human[run.identity["severity"]] for run in runs) / len(runs)
    print(f"  {'human baseline, same work':<28}${mix:>6.2f}")
    print(
        f"  {'agent against baseline':<28}{cost['per_approved'] / mix - 1:>+7.0%}\n"
    )
    print("by severity          attempts  approved   per order  baseline")
    for row in cost_per_outcome(runs, card, human, by=("severity",)):
        print(
            f"  {row['severity']:<18}{row['attempts']:>9,}{row['rate']:>9.0%}"
            f"{row['usd_per_approved']:>11.2f}{row['baseline_usd']:>10.2f}"
            f"  {row['verdict']}"
        )


if __name__ == "__main__":
    main()
