"""Runnable companion code for Chapter 6 of Agentic AI Engineering."""

from .card import NORDBOLT_CARD, build_nordbolt_card, demo_signature_verifier
from .contracts import (
    Approval,
    BillOfMaterials,
    BomLine,
    CommitResult,
    FastenerQuote,
    PurchaseOrder,
    QuoteToolResult,
    TaskOutcome,
)
from .models import MODELS, ModelRegistry

__all__ = [
    "MODELS",
    "NORDBOLT_CARD",
    "Approval",
    "BillOfMaterials",
    "BomLine",
    "CommitResult",
    "FastenerQuote",
    "ModelRegistry",
    "PurchaseOrder",
    "QuoteToolResult",
    "TaskOutcome",
    "build_nordbolt_card",
    "demo_signature_verifier",
]
