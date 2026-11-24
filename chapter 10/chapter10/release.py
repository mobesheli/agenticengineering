"""Rolling out and rolling back: one pointer for each plant, and what it cannot undo."""

from __future__ import annotations

from chapter10.platform import Platform


def canary(platform: Platform, plant: str, bundle: str) -> None:
    """Point one plant at the new bundle. The others stay where they are."""
    platform.note("release", f"{plant}: {platform.endpoints.get(plant)} -> {bundle}")
    platform.endpoints[plant] = bundle


def rollback(platform: Platform, plant: str, bundle: str) -> None:
    platform.note("rollback", f"{plant}: {platform.endpoints.get(plant)} -> {bundle}")
    platform.endpoints[plant] = bundle


def left_behind(platform: Platform, bundle: str, parked: dict[str, str]) -> list[str]:
    """What a rollback from `bundle` does not reverse. Each line needs an owner."""
    orders = [o for o in platform.work_orders.values() if o["bundle"] == bundle]
    memories = [m for m in platform.memory_writes if m["bundle"] == bundle]
    waiting = [run for run, status in parked.items() if status == "waiting"]
    remaining = []
    if memories:
        versions = ", ".join(str(v) for v in sorted({m["schema"] for m in memories}))
        remaining.append(
            f"memory: {len(memories)} written in schema version {versions}"
        )
    if orders:
        numbers = ", ".join(order["number"] for order in orders)
        remaining.append(f"side effects: work orders {numbers} still exist")
    if waiting:
        remaining.append(f"runs in flight: {len(waiting)} waiting for approval")
    return remaining
