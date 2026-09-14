"""Observable counterparty calls that treat correlation as data, not authority."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol


class CounterpartyClient(Protocol):
    def send(self, task: dict[str, Any], *, headers: dict[str, str]) -> Any: ...


def call_counterparty(
    client: CounterpartyClient,
    task: dict[str, Any],
    *,
    tenant: str,
    case_id: str,
    max_attempts: int = 3,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[Any, dict[str, Any]]:
    """Return the reply plus a border-span-shaped receipt."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    started = clock()
    attempt = 0
    while True:
        attempt += 1
        reply = client.send(task, headers={"x-correlation-id": case_id})
        if reply.status != "retry" or attempt >= max_attempts:
            break
    server_info = getattr(reply, "server_info", {}) or {}
    metadata = getattr(reply, "metadata", {}) or {}
    receipt = {
        "tenant": tenant,
        "case_id": case_id,
        "remote_task_id": getattr(reply, "task_id", None),
        "counterparty": server_info.get("name"),
        "counterparty_version": server_info.get("version"),
        "status": reply.status,
        "attempts": attempt,
        "latency_ms": max(0, int((clock() - started) * 1000)),
        "quoted_cost": metadata.get("cost"),
        "receipt_id": metadata.get("receipt_id"),
        "correlation_is_authorization": False,
    }
    return reply, receipt
