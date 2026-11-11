"""Border control: deterministic checks that run before any model sees a request."""

from __future__ import annotations

import re
from typing import Any

from a2a.helpers import get_data_parts
from a2a.types import Message
from google.protobuf.json_format import MessageToDict
from pydantic import ValidationError

from .contracts import ORDER_SKILL, QUOTE_SKILL, BillOfMaterials

ADVERTISED_SKILLS = {QUOTE_SKILL, ORDER_SKILL}
MAX_UNITS_PER_REQUEST = 50_000

INSTRUCTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore (all |any )?(previous|prior|above)",
        r"system (prompt|override|message)",
        r"reveal (your|the) (prompt|instructions)",
        r"you are now",
        r"approve (the|this) (invoice|order)",
    )
]


class BorderRejected(ValueError):
    """An inbound request failed a check and never reached the reasoning core."""


def requested_skill(message: Message) -> str:
    return MessageToDict(message.metadata).get("skill", "")


def structured_payload(message: Message) -> dict[str, Any]:
    payloads = get_data_parts(message.parts)
    if len(payloads) != 1 or not isinstance(payloads[0], dict):
        raise BorderRejected("request must carry exactly one structured data part")
    return payloads[0]


def screen_text(text: str) -> None:
    for pattern in INSTRUCTION_PATTERNS:
        if pattern.search(text):
            raise BorderRejected("free text looks like an instruction")


def admit_quote_request(message: Message) -> BillOfMaterials:
    """Return a validated bill of materials, or refuse at the door."""
    try:
        bom = BillOfMaterials.model_validate(structured_payload(message))
    except ValidationError as exc:
        field = ".".join(str(part) for part in exc.errors()[0]["loc"])
        raise BorderRejected(
            f"request does not match the {QUOTE_SKILL} schema: {field}"
        ) from exc
    if bom.total_units > MAX_UNITS_PER_REQUEST:
        raise BorderRejected("request exceeds the quantity limit for this skill")
    for line in bom.line_items:
        screen_text(line.description)
    return bom
