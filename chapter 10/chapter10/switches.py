"""Six places to stop an agent, and a drill that proves each one works."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from dataclasses import dataclass

from chapter10.platform import Platform, Refused


@dataclass(frozen=True)
class Switch:
    name: str
    owner: str
    pull: Callable[[Platform], None]
    probe: Callable[[Platform], None]
    stops: str


def _gateway(p: Platform) -> None:
    p.budget_usd = 0.0


def _identity(p: Platform) -> None:
    p.identity_enabled = False


def _contract(p: Platform) -> None:
    contract = p.contracts["work-orders"]
    p.contracts["work-orders"] = contract.model_copy(update={"allow": []})


def _runtime(p: Platform) -> None:
    p.endpoints = dict.fromkeys(p.endpoints)


def _register(p: Platform) -> None:
    p.register_status = "suspended"


def _data(p: Platform) -> None:
    p.certified["sensor-history"] = False


def _probe_contract(p: Platform) -> None:
    if "create_work_order" not in p.contracts["work-orders"].allow:
        raise Refused("work-orders.create_work_order: outside contract")


def _probe_runtime(p: Platform) -> None:
    if not any(p.accepts_runs(plant) for plant in p.endpoints):
        raise Refused("runtime: no endpoint accepts new runs")


def _probe_register(p: Platform) -> None:
    if not p.on_marketplace():
        raise Refused("register: not offered to new teams")


SWITCHES = [
    Switch(
        "gateway",
        "platform on-call",
        _gateway,
        Platform.admit_model_call,
        "model calls",
    ),
    Switch(
        "identity",
        "security on-call",
        _identity,
        lambda p: p.check_identity("work-orders"),
        "every tool and data call",
    ),
    Switch("tool contract", "tool owner", _contract, _probe_contract, "one operation"),
    Switch("runtime", "platform on-call", _runtime, _probe_runtime, "new runs"),
    Switch("register", "agent owner", _register, _probe_register, "new adoption"),
    Switch(
        "data supply",
        "data owner",
        _data,
        lambda p: p.check_data("sensor-history"),
        "one data product",
    ),
]


def drill(staging: Platform) -> list[tuple[Switch, bool, float]]:
    """Pull each switch on its own copy of staging and check that it bit."""
    results = []
    for switch in SWITCHES:
        copy_of_staging = copy.deepcopy(staging)
        switch.probe(copy_of_staging)
        started = time.perf_counter()
        switch.pull(copy_of_staging)
        try:
            switch.probe(copy_of_staging)
            stopped = False
        except Refused:
            stopped = True
        results.append((switch, stopped, time.perf_counter() - started))
    return results
