"""Find the agents nobody registered, then watch a listing be refused and earned.

python -m examples.listing_demo
"""

from __future__ import annotations

import yaml

from chapter10.register import (
    DATA,
    RECORDS,
    find_unregistered,
    listing_check,
    load_entry,
    load_register,
    required_evidence,
)


def main() -> list[str]:
    inventory = yaml.safe_load((DATA / "inventory.yaml").read_text())
    registered = load_register()[:1]
    lines = [f"register holds {len(registered)} agent: {registered[0].agent}"]
    lines += [f"  {finding}" for finding in find_unregistered(registered, inventory)]

    lines.append("listing the maintenance planner, tier high")
    for attempt in (1, 2, 3):
        entry = load_entry(DATA / "candidates" / f"attempt-{attempt}.yaml")
        problems = listing_check(entry, required_evidence(entry.tier), RECORDS)
        verdict = "listed" if not problems else "refused: " + "; ".join(problems)
        lines.append(f"  attempt {attempt}  {verdict}")
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    main()
