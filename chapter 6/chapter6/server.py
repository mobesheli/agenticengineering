"""Runnable Starlette A2A server for the NordBolt quoting agent."""

from __future__ import annotations

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from .card import build_nordbolt_card
from .executor import QuoteRunner, QuotingExecutor


def build_app(
    *,
    base_url: str = "http://127.0.0.1:9999",
    runner: QuoteRunner | None = None,
) -> Starlette:
    """Assemble the protocol surface, bridge, and task store."""

    card = build_nordbolt_card(base_url=base_url)
    handler = DefaultRequestHandler(
        agent_executor=QuotingExecutor(runner=runner),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = [
        *create_agent_card_routes(card),
        *create_jsonrpc_routes(handler, "/"),
    ]
    return Starlette(routes=routes)


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9999)
