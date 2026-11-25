"""Day 240: the sweep, the listing check, the reconciliation, and a contract.

python -m examples.fleet_demo
"""

from chapter11.fleet import contract_breaks, listing_gaps, reconcile
from chapter11.settings import load


def main() -> None:
    data = load("fleet")
    register = data["register"]
    swept = [e for e in register if e["found"] == "sweep"]
    print(
        f"on the register: {len(register)} agents, {len(swept)} found by the sweep"
    )
    for entry in register:
        gaps = listing_gaps(entry)
        if len(gaps) > 1:
            print(f"  {entry['agent']:<18} cannot be listed: {len(gaps)} gaps")
    print("\nnightly reconciliation with two vendor registries")
    for finding in reconcile(register, data["vendors"]):
        print(f"  {finding}")
    contract = data["contract"]
    print(f"\n{contract['agent']} moves from contract v2 to v3")
    for name, lost in contract_breaks(
        contract["v3"], contract["registered_consumers"]
    ).items():
        state = f"BREAKS, it reads {', '.join(lost)}" if lost else "passes"
        print(f"  {name:<20} consumer test: {state}")
    for name, lost in contract_breaks(
        contract["v3"], contract["unregistered_callers"]
    ).items():
        print(
            f"  {name:<20} not registered, so no test: reads {', '.join(lost)}"
        )


if __name__ == "__main__":
    main()
