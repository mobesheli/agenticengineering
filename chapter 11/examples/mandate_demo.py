"""A spending mandate at work, and what revoking it does and does not do.

python -m examples.mandate_demo
"""

from chapter11.mandate import Mandate, authorize, revoke
from chapter11.settings import load


def main() -> None:
    data = load("mandate")
    terms = data["mandate"]
    mandate = Mandate(**{**terms, "suppliers": tuple(terms["suppliers"])})
    print(
        f"{mandate.agent}: up to ${mandate.cap_per_order:.0f} an order and"
        f" ${mandate.cap_per_day:.0f} a day, {len(mandate.suppliers)} suppliers"
        f"\n  on {mandate.instrument}, expires day {mandate.expires_day}"
        f"\n  signed by the {mandate.signed_by}"
    )
    for order in data["orders"]:
        refusal = authorize(order, mandate)
        print(f"  {order['id']}  ${order['usd']:<4} {order['supplier']}")
        print("        " + (f"refused: {refusal}" if refusal else "placed"))
    open_orders = revoke(mandate)
    print("\nmandate revoked")
    for order in data["after_revocation"]:
        print(f"  {order['id']}  refused: {authorize(order, mandate)}")
    total = sum(order["usd"] for order in open_orders)
    names = ", ".join(order["id"] for order in open_orders)
    print(f"  still placed and not undone: {names} (${total:.0f})")
    print("  each needs a person: cancel with the supplier, or let it complete")


if __name__ == "__main__":
    main()
