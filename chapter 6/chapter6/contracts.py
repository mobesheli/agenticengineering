"""The typed contracts that cross the organizational boundary in Chapter 6."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

QUOTE_SKILL = "quote-fasteners"
ORDER_SKILL = "accept-order"

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
    sku: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0, le=100_000)
    custom: bool = False
    drawing_rev: str | None = Field(default=None, max_length=8)


class BillOfMaterials(BaseModel):
    commodity: str = Field(min_length=1, max_length=60)
    requested_delivery_date: date
    line_items: list[BomLine] = Field(min_length=1, max_length=100)

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.line_items)

    @property
    def has_custom_parts(self) -> bool:
        return any(line.custom for line in self.line_items)

    def lines_missing_drawing(self) -> list[str]:
        return [
            line.sku for line in self.line_items if line.custom and not line.drawing_rev
        ]


class FastenerQuote(BaseModel):
    quote_id: str
    unit_price: float = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    lead_time_days: int = Field(gt=0)
    valid_until: date
    conditions: list[str] = Field(default_factory=list)


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

    def to_payload(self, approval_reference: str) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["approval_reference"] = approval_reference
        return payload


class OrderConfirmation(BaseModel):
    confirmation: str
    po_number: str
    quote_id: str
    accepted: bool


class Approval(BaseModel):
    reference: str
    approved_by: str
    po_number: str
    maximum_amount: float = Field(gt=0)
    expires_on: date

    def authorizes(self, po: PurchaseOrder, today: date) -> bool:
        return (
            self.po_number == po.po_number
            and po.total_value <= self.maximum_amount
            and today <= self.expires_on
        )


class TaskOutcome(BaseModel):
    task_id: str
    state: TaskStateName
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None


class QuoteToolResult(BaseModel):
    ok: bool
    supplier_id: str
    error_class: str | None = None
    retryable: bool = False
    detail: str | None = None
    task_id: str | None = None
    quote: FastenerQuote | None = None

    @model_validator(mode="after")
    def result_is_coherent(self) -> QuoteToolResult:
        if self.ok != (self.quote is not None):
            raise ValueError("a result carries a quote exactly when it succeeded")
        if self.ok and self.error_class is not None:
            raise ValueError("a successful result cannot carry an error class")
        return self


class CommitResult(BaseModel):
    committed: bool
    reason: str | None = None
    confirmation: str | None = None
    task_id: str | None = None
