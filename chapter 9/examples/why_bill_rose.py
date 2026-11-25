"""Why the invoice tripled while the price of a token halved.

python -m examples.why_bill_rose
"""

import yaml

from chapter9.month import load_month
from chapter9.pricecard import load_price_card
from chapter9.report import bill_change, metrics, reconcile
from chapter9.settings import DATA


def main() -> None:
    card = load_price_card()
    earlier = yaml.safe_load((DATA / "earlier.yaml").read_text())
    invoice = yaml.safe_load((DATA / "invoice.yaml").read_text())
    _, runs = load_month("before", card)
    change = bill_change(earlier, runs)
    print("quarter on quarter, monthly averages")
    print(f"  runs               x{change['runs_x']:.2f}")
    print(f"  tokens per run     x{change['tokens_per_run_x']:.2f}")
    print(f"  price per token    x{change['usd_per_million_tokens_x']:.2f}")
    print(
        f"  token bill         x{change['bill_x']:.2f}   "
        f"${change['bill_before']:,.0f} to ${change['bill_now']:,.0f}"
    )
    check = reconcile(runs, invoice["token_charges_usd"], invoice["tolerance"])
    state = "within" if check["within_tolerance"] else "OUTSIDE"
    print(
        f"\nledger ${check['ledger_usd']:,.2f} against invoice ${check['invoice_usd']:,.2f}:"
        f" gap {check['gap']:.1%}, {state} the {invoice['tolerance']:.0%} tolerance"
    )
    for name in ("before", "after"):
        month, runs = load_month(name, card)
        seen = metrics(runs)
        print(f"\n{month['label']}")
        print(
            f"  turns per run, median and 95th percentile  {seen['turns_p50']} and {seen['turns_p95']}"
        )
        print(
            f"  runs with a repeated call that executed    {seen['loop_rate']:.1%}"
        )
        print(
            f"  runs with a repeated call that was refused {seen['refused_repeat_rate']:.1%}"
        )
        print(
            f"  tool calls that failed                     {seen['tool_failure_rate']:.1%}"
        )
        print(
            f"  input tokens read from the cache           {seen['cache_hit_rate']:.0%}"
        )
        print(
            f"  tokens per run                             {seen['tokens_per_run']:,.0f}"
        )


if __name__ == "__main__":
    main()
