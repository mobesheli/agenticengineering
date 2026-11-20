"""Run two invoices through the code-led workflow.

python -m examples.invoice              # needs OPENAI_API_KEY
python -m examples.invoice --scripted   # no key: scripted model replies
"""

import asyncio
import sys

from chapter5 import invoices
from chapter5.invoices import Books, process_invoice

INVOICES = [
    "Invoice 2291 from Kessler Werkzeug GmbH. Total due: 4,820.00 EUR.",
    "Invoice 2305 from Kessler Werkzeug GmbH. Total due: 48,200.00 EUR.",
]


async def main(scripted_run: bool = False) -> Books:
    if scripted_run:
        from examples.scripted import says, scripted

        invoices.extractor = scripted(
            invoices.extractor,
            says(
                {
                    "vendor": "Kessler Werkzeug GmbH",
                    "amount": "4820.00",
                    "currency": "EUR",
                }
            ),
            says(
                {
                    "vendor": "Kessler Werkzeug GmbH",
                    "amount": "48200.00",
                    "currency": "EUR",
                }
            ),
        )
    books = Books()
    for text in INVOICES:
        print(await process_invoice(text, books))
    return books


if __name__ == "__main__":
    asyncio.run(main(scripted_run="--scripted" in sys.argv))
