"""The buyer's webhook: where counterparties report progress on long-running tasks."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

TOKEN_HEADER = "X-A2A-Notification-Token"
MAX_HELD = 200


def describe(event: dict[str, Any]) -> tuple[str, str, str]:
    """Reduce a notification to its task, what changed, and an identity for dedupe."""
    if "artifactUpdate" in event:
        update = event["artifactUpdate"]
        return update["taskId"], "artifact", update["artifact"]["artifactId"]
    if "statusUpdate" in event:
        task_id, status = (
            event["statusUpdate"]["taskId"],
            event["statusUpdate"]["status"],
        )
    else:
        task_id, status = event["task"]["id"], event["task"]["status"]
    return task_id, status["state"], status.get("timestamp", "")


@dataclass
class NotificationInbox:
    tokens: dict[str, str]
    open_tasks: dict[str, str] = field(default_factory=dict)
    seen: set[tuple[str, str, str]] = field(default_factory=set)
    work_queue: list[tuple[str, str, str]] = field(default_factory=list)
    held: list[tuple[str, str, str, str]] = field(default_factory=list)

    def expect(self, counterparty_id: str, task_id: str) -> None:
        """Record a task we opened, and release what arrived before we knew its ID."""
        self.open_tasks[task_id] = counterparty_id
        early = [item for item in self.held if item[:2] == (counterparty_id, task_id)]
        self.held = [item for item in self.held if item not in early]
        for item in early:
            self._enqueue(*item)

    def _enqueue(self, sender: str, task_id: str, change: str, identity: str) -> None:
        if (task_id, change, identity) not in self.seen:
            self.seen.add((task_id, change, identity))
            self.work_queue.append((sender, task_id, change))

    async def receive(self, request: Request) -> Response:
        sender = request.path_params["counterparty_id"]
        token = self.tokens.get(sender)
        presented = request.headers.get(TOKEN_HEADER, "")
        if not token or not hmac.compare_digest(presented, token):
            return Response(status_code=401)
        task_id, change, identity = describe(await request.json())
        if self.open_tasks.get(task_id) == sender:
            self._enqueue(sender, task_id, change, identity)
        elif task_id not in self.open_tasks and len(self.held) < MAX_HELD:
            self.held.append((sender, task_id, change, identity))
        else:
            return Response(status_code=404)
        return Response(status_code=204)


def build_webhook(inbox: NotificationInbox) -> Starlette:
    route = Route(
        "/a2a/notifications/{counterparty_id}", inbox.receive, methods=["POST"]
    )
    return Starlette(routes=[route])
