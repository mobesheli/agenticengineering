"""Code-led control: the model extracts, the code decides what happens next."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from agents import Agent, Runner
from pydantic import BaseModel

from chapter5.models import MODELS, QUICK


@dataclass
class Books:
    """A stand-in for the finance system: a ledger and a review queue."""

    ledger: list[ExtractedInvoice] = field(default_factory=list)
    review_queue: list[ExtractedInvoice] = field(default_factory=list)

    async def post_to_ledger(self, invoice: ExtractedInvoice) -> str:
        self.ledger.append(invoice)
        return f"posted {invoice.vendor} {invoice.amount:.2f} {invoice.currency}"

    async def route_to_review(self, invoice: ExtractedInvoice) -> str:
        self.review_queue.append(invoice)
        return f"review {invoice.vendor} {invoice.amount:.2f} {invoice.currency}"


class ExtractedInvoice(BaseModel):
    vendor: str
    amount: Decimal
    currency: str


extractor = Agent(
    name="invoice_extractor",
    model=MODELS.small,
    model_settings=QUICK,
    instructions="Extract the vendor, amount, and currency from the invoice text.",
    output_type=ExtractedInvoice,
)

REVIEW_ABOVE = Decimal(10000)


async def process_invoice(raw_text: str, books: Books) -> str:
    extraction = await Runner.run(extractor, raw_text, max_turns=1)
    invoice = extraction.final_output
    if invoice.amount > REVIEW_ABOVE:
        return await books.route_to_review(invoice)
    return await books.post_to_ledger(invoice)
