"""Where the model spend goes, by step and by model.

python -m examples.token_share
"""

from chapter9.month import load_month
from chapter9.pricecard import load_price_card
from chapter9.report import token_share_by_step


def main() -> None:
    card = load_price_card()
    for name in ("before", "after"):
        month, runs = load_month(name, card)
        print(f"{month['label']}\n  {month['config']}")
        print(
            "  step   model            input tokens  cached  reasoning    spend  share"
        )
        for row in token_share_by_step(runs):
            print(
                f"  {row['step']:<6} {row['model']:<15}{row['input'] / 1e6:>11.0f} M"
                f"{row['cached'] / row['input']:>8.0%}{row['reasoning'] / 1e6:>9.1f} M"
                f"{row['usd']:>9,.0f}{row['share']:>7.0%}"
            )
        print()


if __name__ == "__main__":
    main()
