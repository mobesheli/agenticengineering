"""Serve a quoting agent over A2A: a signed card and a JSON-RPC task endpoint."""

from __future__ import annotations

import httpx
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCard
from agents import Agent
from starlette.applications import Starlette

from .agent import quote_agent
from .card import build_card, sign_card
from .executor import QuotingExecutor
from .ledger import SupplierLedger


def build_app(
    card: AgentCard,
    agent: Agent = quote_agent,
    ledger: SupplierLedger | None = None,
    outbound: httpx.AsyncClient | None = None,
) -> Starlette:
    push_configs = InMemoryPushNotificationConfigStore()
    handler = DefaultRequestHandler(
        agent_executor=QuotingExecutor(agent, ledger),
        task_store=InMemoryTaskStore(),
        agent_card=card,
        push_config_store=push_configs,
        push_sender=BasePushNotificationSender(
            outbound or httpx.AsyncClient(), push_configs
        ),
    )
    card_routes = create_agent_card_routes(card)
    return Starlette(routes=[*card_routes, *create_jsonrpc_routes(handler, "/a2a")])


if __name__ == "__main__":
    import uvicorn

    local_card = sign_card(
        build_card(base_url="http://127.0.0.1:9999"), kid="nordbolt-2026-01"
    )
    uvicorn.run(build_app(local_card), host="127.0.0.1", port=9999)
