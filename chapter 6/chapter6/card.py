"""Agent Card construction, signing, and fingerprinting."""

from __future__ import annotations

import hashlib
import json

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    ClientCredentialsOAuthFlow,
    OAuth2SecurityScheme,
    OAuthFlows,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)
from a2a.utils.signing import create_agent_card_signer
from google.protobuf.json_format import MessageToDict

from .contracts import ORDER_SKILL, QUOTE_SKILL
from .keys import private_pem

JSON_MODE = "application/json"


def quote_skill() -> AgentSkill:
    return AgentSkill(
        id=QUOTE_SKILL,
        name="Quote fastener order",
        description="Prices a bill of materials and returns a dated quote.",
        tags=["procurement", "fasteners", "quote"],
        examples=["Quote 2,000 custom brackets for delivery in six weeks."],
    )


def order_skill() -> AgentSkill:
    return AgentSkill(
        id=ORDER_SKILL,
        name="Accept purchase order",
        description="Accepts a purchase order that matches a quote this agent issued.",
        tags=["procurement", "fasteners", "order"],
        examples=["Accept purchase order PO-88231 against quote NB-7F3A."],
    )


def oauth_scheme(token_url: str) -> SecurityScheme:
    flow = ClientCredentialsOAuthFlow(
        token_url=token_url,
        scopes={"quotes:request": "Request quotes and place orders"},
    )
    return SecurityScheme(
        oauth2_security_scheme=OAuth2SecurityScheme(
            flows=OAuthFlows(client_credentials=flow)
        )
    )


def build_card(
    *,
    name: str = "nordbolt-quoting-agent",
    organization: str = "NordBolt Industrial Fasteners",
    base_url: str = "https://agents.nordbolt.example",
    version: str = "1.4.0",
) -> AgentCard:
    domain = base_url.split("//", 1)[1].split("/", 1)[0]
    return AgentCard(
        name=name,
        description="Quotes industrial fasteners and takes orders against its quotes.",
        version=version,
        provider=AgentProvider(organization=organization, url=f"https://{domain}"),
        supported_interfaces=[
            AgentInterface(
                url=f"{base_url}/a2a",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(streaming=True, push_notifications=True),
        default_input_modes=[JSON_MODE],
        default_output_modes=[JSON_MODE],
        skills=[quote_skill(), order_skill()],
        security_schemes={"oauth": oauth_scheme(f"https://{domain}/oauth/token")},
        security_requirements=[
            SecurityRequirement(schemes={"oauth": StringList(list=["quotes:request"])})
        ],
    )


def sign_card(card: AgentCard, kid: str) -> AgentCard:
    header = {"kid": kid, "alg": "ES256", "typ": "JOSE"}
    signer = create_agent_card_signer(private_pem(kid), protected_header=header)
    return signer(card)


def card_to_json(card: AgentCard) -> dict:
    return MessageToDict(card)


def card_fingerprint(card: AgentCard) -> str:
    """Hash the card's content. Signatures are excluded, so a routine key
    rotation does not change the fingerprint, and a changed promise does."""
    content = card_to_json(card)
    content.pop("signatures", None)
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
