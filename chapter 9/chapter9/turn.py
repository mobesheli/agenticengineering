"""The anatomy of one turn: what the model reads and writes, and the cost."""

from __future__ import annotations

from dataclasses import dataclass

from chapter9.meter import TurnCost, price_usage, usage_of
from chapter9.pricecard import Rates


@dataclass(frozen=True)
class Turn:
    """Token counts for one turn late in a run, before any optimization."""

    instructions: int = 1_500
    tool_definitions: int = 12_000
    history: int = 20_000
    new_material: int = 1_500
    output: int = 2_000
    reasoning: int = 1_200
    tools_loaded_when_deferred: int = 2_000

    @property
    def prefix(self) -> int:
        return self.instructions + self.tool_definitions + self.history


def variants(turn: Turn, rates: Rates) -> dict[str, TurnCost]:
    full = turn.prefix + turn.new_material
    lean = full - turn.tool_definitions + turn.tools_loaded_when_deferred
    tail = 2_000
    shapes = {
        "nothing cached": usage_of(full, turn.output, reasoning=turn.reasoning),
        "tools deferred, nothing cached": usage_of(
            lean, turn.output, reasoning=turn.reasoning
        ),
        "prefix cached": usage_of(
            full, turn.output, turn.prefix - tail, tail, turn.reasoning
        ),
        "prefix changed, cache rewritten": usage_of(
            full, turn.output, 0, turn.prefix, turn.reasoning
        ),
    }
    return {name: price_usage(usage, rates) for name, usage in shapes.items()}
