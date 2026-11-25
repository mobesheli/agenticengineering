"""Shared set-up for the examples: price card, ledger, and baseline."""

from __future__ import annotations

import yaml
from agents import Model
from agents.tracing import set_trace_processors

from chapter9.budget import RunBudget
from chapter9.ledger import Ledger, ModelCall, RunRecord
from chapter9.metered import MeteredModel, StepRouter
from chapter9.planner import build_agents
from chapter9.pricecard import PriceCard, load_price_card
from chapter9.settings import DATA, FRONTIER, MODELS


def start() -> tuple[PriceCard, Ledger]:
    card = load_price_card()
    ledger = Ledger(card)
    set_trace_processors([ledger])
    return card, ledger


def baseline() -> dict[str, float]:
    return yaml.safe_load((DATA / "baseline.yaml").read_text())[
        "usd_per_approved_order"
    ]


def frontier_agents(
    diagnose: Model,
    draft: Model,
    card: PriceCard,
    budget: RunBudget,
    guarded: bool,
):
    """Every step on the frontier model."""
    return build_agents(
        MeteredModel(diagnose, FRONTIER, card, budget),
        MeteredModel(draft, FRONTIER, card, budget, "draft"),
        card,
        guarded,
    )


def routed_agents(
    plan: Model, read: Model, draft: Model, card: PriceCard, budget: RunBudget
):
    """Each step on the model chosen for it."""
    router = StepRouter(
        {
            "plan": MeteredModel(plan, MODELS["plan"], card, budget),
            "read": MeteredModel(read, MODELS["read"], card, budget),
        }
    )
    drafter = MeteredModel(draft, MODELS["draft"], card, budget, "draft")
    return build_agents(router, drafter, card)


def in_order(events: list) -> list:
    """Tools that ran side by side finish in any order. Print them by name."""
    ordered, batch = [], []
    for event in events:
        if isinstance(event, ModelCall):
            ordered += sorted(batch, key=lambda call: call.name) + [event]
            batch = []
        else:
            batch.append(event)
    return ordered + sorted(batch, key=lambda call: call.name)


def show(run: RunRecord) -> None:
    print(
        "  step   model or tool          input  cached  output"
        "  reasoning     cost"
    )
    for event in in_order(run.events):
        if isinstance(event, ModelCall):
            print(
                f"  {event.step:<6} {event.model:<19}{event.input_tokens:>9,}"
                f"{event.cached_tokens:>8,}{event.output_tokens:>8,}"
                f"{event.reasoning_tokens:>11,}  ${event.cost_usd:.4f}"
            )
        else:
            note = "refused: repeat" if event.refused else ""
            note = "stopped: budget" if event.stopped else note
            note = note or ("repeat of the call above" if event.repeat else "")
            print(f"  tool   {event.name:<19}  {note:<34}  ${event.fee_usd:.4f}")
    print(
        f"  model ${run.model_usd:.4f}  tools ${run.tool_usd:.4f}  "
        f"turns {run.turns}  repeated calls {run.repeats}"
    )
