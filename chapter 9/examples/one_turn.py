"""What one turn late in a run costs, four ways, on the price card.

python -m examples.one_turn
"""

from dataclasses import asdict

from chapter9.pricecard import load_price_card
from chapter9.settings import MODELS
from chapter9.turn import Turn, variants


def main() -> None:
    card, turn = load_price_card(), Turn()
    model = MODELS["read"]
    read = turn.prefix + turn.new_material
    print(f"turn 8 on {model}, price card {card.version}")
    print(
        f"reads {read:,} tokens: instructions {turn.instructions:,}, "
        f"tool definitions {turn.tool_definitions:,},"
    )
    print(f"  history {turn.history:,}, new material {turn.new_material:,}")
    print(
        f"writes {turn.output:,} tokens, of which {turn.reasoning:,} are reasoning\n"
    )
    print(
        f"{'':<32}{'input':>8}{'cached':>8}{'write':>8}{'reason':>8}{'answer':>8}{'total':>8}"
    )
    for name, cost in variants(turn, card.rates(model)).items():
        cells = "".join(f"{usd:>8.4f}" for usd in asdict(cost).values())
        print(f"{name:<32}{cells}{cost.total:>8.4f}")


if __name__ == "__main__":
    main()
