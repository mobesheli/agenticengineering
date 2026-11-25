"""The border span: your own record of a call to another organization's agent."""

from __future__ import annotations

import time
from typing import Any

from agents import custom_span


async def call_counterparty(client: Any, task: dict, case_id: str) -> Any:
    started, attempts = time.monotonic(), 0
    sent = {"case_id": case_id, "counterparty": client.name}
    with custom_span(f"border.{client.name}", sent) as span:
        while True:
            attempts += 1
            reply = await client.send(
                task, headers={"x-correlation-id": case_id}
            )
            if reply.status != "retry" or attempts >= 3:
                break
        span.span_data.data.update(
            {
                "remote_task_id": reply.task_id,
                "reported_version": reply.server.get("version"),
                "status": reply.status,
                "attempts": attempts,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "quoted_cost_usd": reply.metadata.get("cost_usd"),
                "receipt_id": reply.metadata.get("receipt_id"),
            }
        )
    return reply
