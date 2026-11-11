"""A two-supplier neighborhood that runs in one process, for the drills and tests.

Each supplier is a real A2A server (signed card, JSON-RPC endpoint, executor,
Agents SDK runner). The only thing replaced is the model: the drills drive the
runner through the SDK's scripted test model, so they need no API key and
produce the same output every time. The HTTP client routes each supplier's
hostname to its in-process application.
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx
from a2a.types import AgentCard, TaskPushNotificationConfig
from agents import set_tracing_disabled
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from starlette.applications import Starlette

from .agent import build_quote_agent
from .card import build_card, card_fingerprint, sign_card
from .keys import public_pem
from .ledger import SupplierLedger
from .registry import (
    COUNTERPARTIES,
    CounterpartyEntry,
    CounterpartyRegistry,
    SigningKey,
    TrustRecord,
)
from .server import build_app
from .webhook import NotificationInbox, build_webhook

COMMODITIES = frozenset({"custom-brackets", "industrial-fasteners"})
BUYER_HOST = "procurement.halden-works.example"


@dataclass(frozen=True)
class SupplierProfile:
    id: str
    organization: str
    host: str
    kid: str
    quote_prefix: str
    lead_time_days: int
    price_factor: float
    supplier_score: float
    previous_kids: tuple[str, ...] = ()

    @property
    def base_url(self) -> str:
        return f"https://{self.host}"


NORDBOLT = SupplierProfile(
    id="nordbolt",
    organization="NordBolt Industrial Fasteners",
    host="agents.nordbolt.example",
    kid="nordbolt-2026-01",
    quote_prefix="NB",
    lead_time_days=28,
    price_factor=1.0,
    supplier_score=0.96,
    previous_kids=("nordbolt-2025-01",),
)
RIVETRIDGE = SupplierProfile(
    id="rivetridge",
    organization="RivetRidge Components",
    host="agents.rivetridge.example",
    kid="rivetridge-2026-01",
    quote_prefix="RR",
    lead_time_days=24,
    price_factor=1.05,
    supplier_score=0.91,
)


def scripted_quoter(profile: SupplierProfile, runs: int = 8) -> ScriptedModel:
    """A scripted model that behaves like a quoting agent: two tool calls, one quote."""

    def first_turn(call):
        bom = json.loads(_first_user_text(call.input))
        units = sum(line["quantity"] for line in bom["line_items"])
        custom = any(line.get("custom") for line in bom["line_items"])
        first = bom["line_items"][0]
        return [
            function_call(
                "check_inventory",
                {"sku": first["sku"], "quantity": units},
                call_id="inv",
            ),
            function_call(
                "price_order", {"total_units": units, "custom": custom}, call_id="price"
            ),
        ]

    def second_turn(call):
        price = ast.literal_eval(_tool_output(call.input, "price"))["unit_price"]
        digest = (
            hashlib.sha256(_first_user_text(call.input).encode())
            .hexdigest()[:6]
            .upper()
        )
        quote = {
            "quote_id": f"{profile.quote_prefix}-{digest}",
            "unit_price": round(price * profile.price_factor, 2),
            "currency": "GBP",
            "lead_time_days": profile.lead_time_days,
            "valid_until": (date.today() + timedelta(days=14)).isoformat(),
            "conditions": ["Subject to material availability at order acceptance."],
        }
        return [assistant_message(json.dumps(quote))]

    steps = []
    for _ in range(runs):
        steps += [ModelStep.respond(first_turn), ModelStep.respond(second_turn)]
    return ScriptedModel(steps)


def _first_user_text(items) -> str:
    if isinstance(items, str):
        return items
    for item in items:
        if item.get("role") == "user":
            content = item["content"]
            return content if isinstance(content, str) else content[0]["text"]
    raise ValueError("no user input in the model call")


def _tool_output(items, call_id: str) -> str:
    for item in items:
        if (
            item.get("type") == "function_call_output"
            and item.get("call_id") == call_id
        ):
            output = item["output"]
            return output if isinstance(output, str) else output[0]["text"]
    raise ValueError(f"no output recorded for tool call {call_id}")


class SwitchableTransport(httpx.AsyncBaseTransport):
    """Routes to an in-process app, and can be switched off to simulate an outage."""

    def __init__(self, app: Starlette) -> None:
        self._inner = httpx.ASGITransport(app=app)
        self.online = True

    def serve(self, app: Starlette) -> None:
        self._inner = httpx.ASGITransport(app=app)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not self.online:
            raise httpx.ConnectError("connection refused", request=request)
        return await self._inner.handle_async_request(request)


@dataclass
class Supplier:
    profile: SupplierProfile
    card: AgentCard
    model: ScriptedModel
    ledger: SupplierLedger
    transport: SwitchableTransport


@dataclass
class Neighborhood:
    suppliers: dict[str, Supplier] = field(default_factory=dict)
    http: httpx.AsyncClient | None = None
    inbox: NotificationInbox | None = None
    outbound: httpx.AsyncClient | None = None

    def __getitem__(self, supplier_id: str) -> Supplier:
        return self.suppliers[supplier_id]

    def serve(
        self, supplier_id: str, card: AgentCard | None = None, agent=None
    ) -> None:
        """Replace what a supplier is serving: a different card, or a different agent."""
        supplier = self.suppliers[supplier_id]
        agent = agent or build_quote_agent(f"{supplier_id}_quoting", supplier.model)
        app = build_app(card or supplier.card, agent, supplier.ledger, self.outbound)
        supplier.transport.serve(app)

    async def aclose(self) -> None:
        for client in (self.http, self.outbound):
            if client is not None:
                await client.aclose()


def start_supplier(
    profile: SupplierProfile, outbound: httpx.AsyncClient | None = None
) -> Supplier:
    card = sign_card(
        build_card(
            name=f"{profile.id}-quoting-agent",
            organization=profile.organization,
            base_url=profile.base_url,
        ),
        kid=profile.kid,
    )
    model = scripted_quoter(profile)
    ledger = SupplierLedger()
    agent = build_quote_agent(name=f"{profile.id}_quoting", model=model)
    transport = SwitchableTransport(build_app(card, agent, ledger, outbound))
    return Supplier(profile, card, model, ledger, transport)


def approve(
    profile: SupplierProfile,
    card: AgentCard,
    *,
    agent_url: str | None = None,
    approved_by: str = "procurement-security-board",
) -> CounterpartyEntry:
    """What the onboarding review produces: a trust record and the terms of waiting."""
    today = date.today()
    keys = [
        SigningKey(
            profile.kid,
            public_pem(profile.kid),
            today - timedelta(days=30),
            today + timedelta(days=335),
        )
    ]
    keys += [
        SigningKey(
            kid,
            public_pem(kid),
            today - timedelta(days=395),
            today + timedelta(days=30),
        )
        for kid in profile.previous_kids
    ]
    trust = TrustRecord(
        organization=profile.organization,
        agent_url=agent_url or profile.base_url,
        card_version=card.version,
        card_fingerprint=card_fingerprint(card),
        signing_keys=tuple(keys),
        trust_anchor=f"Public key exchanged under MSA-{profile.id.upper()}-2026, schedule C",
        contract_reference=f"MSA-{profile.id.upper()}-2026",
        approved_by=approved_by,
        approved_on=today,
    )
    return CounterpartyEntry(
        id=profile.id,
        trust=trust,
        commodity_codes=COMMODITIES,
        sla_seconds=5.0,
        supplier_score=profile.supplier_score,
    )


def build_neighborhood(registry: CounterpartyRegistry = COUNTERPARTIES) -> Neighborhood:
    set_tracing_disabled(True)
    registry.clear()
    hood = Neighborhood(inbox=NotificationInbox(tokens={}))
    webhook = httpx.ASGITransport(app=build_webhook(hood.inbox))
    hood.outbound = httpx.AsyncClient(mounts={f"all://{BUYER_HOST}": webhook})
    mounts = {}
    for profile in (NORDBOLT, RIVETRIDGE):
        supplier = start_supplier(profile, hood.outbound)
        hood.suppliers[profile.id] = supplier
        entry = approve(profile, supplier.card)
        token = f"demo-webhook-token-{profile.id}"
        hood.inbox.tokens[profile.id] = token
        entry.webhook = TaskPushNotificationConfig(
            url=f"https://{BUYER_HOST}/a2a/notifications/{profile.id}", token=token
        )
        registry.onboard(entry)
        mounts[f"all://{profile.host}"] = supplier.transport
    hood.http = httpx.AsyncClient(mounts=mounts)
    return hood
