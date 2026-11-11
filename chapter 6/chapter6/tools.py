"""The remote agent as a function tool, for steps where a model picks the supplier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents import RunContextWrapper, function_tool

from .contracts import QuoteToolResult
from .remote import Delegation, request_supplier_quote


@dataclass
class SourcingContext:
    via: Delegation
    bom: dict[str, Any]


@function_tool
async def ask_supplier_for_quote(
    ctx: RunContextWrapper[SourcingContext], supplier_id: str
) -> QuoteToolResult:
    """Ask one approved supplier agent to quote the current bill of materials."""
    sourcing = ctx.context
    return await request_supplier_quote(sourcing.via, supplier_id, sourcing.bom)
