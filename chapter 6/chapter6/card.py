"""Agent Card construction, signing, and registry-side verification."""

from __future__ import annotations

import hashlib

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
from a2a.utils.signing import create_agent_card_signer, create_signature_verifier
from google.protobuf.json_format import MessageToDict

# A deliberately public teaching key. Production signing keys belong in a KMS.
DEMO_SIGNING_KEY = b"chapter-6-demo-key-is-not-a-production-secret"
DEMO_KEY_ID = "nordbolt-demo-2026-01"


def build_nordbolt_card(
    *,
    base_url: str = "http://127.0.0.1:9999",
    signing_key: bytes = DEMO_SIGNING_KEY,
    sign: bool = True,
) -> AgentCard:
    """Build the narrow, public contract advertised by NordBolt."""

    oauth = SecurityScheme(
        oauth2_security_scheme=OAuth2SecurityScheme(
            flows=OAuthFlows(
                client_credentials=ClientCredentialsOAuthFlow(
                    token_url="https://identity.nordbolt.example/oauth/token",
                    scopes={"quotes:request": "Request fastener quotes"},
                )
            )
        )
    )
    card = AgentCard(
        name="nordbolt-quoting-agent",
        description=(
            "Quotes price and lead time for industrial fasteners against a "
            "submitted bill of materials."
        ),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=base_url,
                protocol_version="1.0",
            )
        ],
        provider=AgentProvider(
            organization="NordBolt Industrial Fasteners",
            url="https://nordbolt.example",
        ),
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True, push_notifications=True),
        security_schemes={"oauth": oauth},
        security_requirements=[
            SecurityRequirement(schemes={"oauth": StringList(list=["quotes:request"])})
        ],
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="quote-fasteners",
                name="Quote fastener order",
                description=(
                    "Returns a priced quote with a validity window for standard "
                    "and custom fasteners."
                ),
                tags=["procurement", "fasteners", "quote"],
                examples=["Quote this bill of materials for delivery in six weeks."],
                input_modes=["application/json"],
                output_modes=["application/json"],
            )
        ],
    )
    if not sign:
        return card
    signer = create_agent_card_signer(
        signing_key,
        protected_header={"kid": DEMO_KEY_ID, "alg": "HS256", "typ": "JOSE"},
    )
    return signer(card)


def demo_signature_verifier(signing_key: bytes = DEMO_SIGNING_KEY):
    """Return the verifier an allowlisted registry would give the A2A client."""

    def key_provider(kid: str | None, _jku: str | None) -> bytes:
        if kid != DEMO_KEY_ID:
            raise KeyError(f"untrusted signing key: {kid}")
        return signing_key

    return create_signature_verifier(key_provider, algorithms=["HS256"])


def card_fingerprint(card: AgentCard) -> str:
    """Create a stable audit fingerprint without treating it as a signature."""

    card_dict = MessageToDict(card, preserving_proto_field_name=False)
    return hashlib.sha256(repr(sorted(card_dict.items())).encode()).hexdigest()


NORDBOLT_CARD = build_nordbolt_card()
