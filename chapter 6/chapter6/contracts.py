"""Typed contracts that cross the Chapter 6 organizational boundary."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TaskStateName = Literal[
    "submitted",
    "working",
    "completed",
    "failed",
    "canceled",
    "rejected",
    "input_required",
    "auth_required",
]


class BomLine(BaseModel):
    sku: str = Field(min_length=1)
    description: str = Field(min_length=1)
    quantity: int = Field(gt=0, le=100_000)


class BillOfMaterials(BaseModel):
    commodity: str = Field(min_length=1)
    requested_delivery_date: date
    line_items: list[BomLine] = Field(min_length=1, max_length=100)

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.line_items)


class FastenerQuote(BaseModel):
    quote_id: str
    supplier_id: str
    unit_price: float = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    lead_time_days: int = Field(gt=0)
    valid_until: date
    conditions: list[str] = Field(default_factory=list)


class QuoteToolResult(BaseModel):
    ok: bool
    error_class: str | None = None
    retryable: bool = False
    quote: FastenerQuote | None = None

    @model_validator(mode="after")
    def result_is_coherent(self) -> QuoteToolResult:
        if self.ok != (self.quote is not None):
            raise ValueError(
                "successful results require a quote; failures must not contain one"
            )
        if self.ok and self.error_class is not None:
            raise ValueError("successful results cannot contain an error class")
        return self


class TaskOutcome(BaseModel):
    task_id: str
    state: TaskStateName
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None


class PurchaseOrder(BaseModel):
    po_number: str
    supplier_id: str
    quote_id: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    delivery_date: date

    @property
    def total_value(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    def to_signed_payload(self, approval_reference: str) -> str:
        """Return the scoped commitment envelope used by the demo counterparty."""

        payload = self.model_dump(mode="json")
        payload["approvalReference"] = approval_reference
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class Approval(BaseModel):
    reference: str
    approved_by: str
    po_number: str
    maximum_amount: float = Field(gt=0)

    def authorizes(self, po: PurchaseOrder) -> bool:
        return self.po_number == po.po_number and po.total_value <= self.maximum_amount


class CommitResult(BaseModel):
    committed: bool
    reason: str | None = None
    confirmation: str | None = None


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: str
    counterparty_id: str
    task_id: str
    request_hash: str
    response_hash: str
    identity: str
    card_version: str
