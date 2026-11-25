"""The fleet: what a listing needs, what two registries disagree on, and
whether a contract change breaks the agents that call it."""

from __future__ import annotations

NEEDS = {
    "sponsor": "no named sponsor",
    "identity_scoped": "no scoped identity of its own",
    "card": "no agent card",
    "ceiling": "no ceiling",
    "retire_when": "no condition for retiring it",
}


def listing_gaps(entry: dict) -> list[str]:
    return [
        why for name, why in NEEDS.items() if entry.get(name) in (None, False)
    ]


def reconcile(register: list[dict], vendors: dict[str, list[str]]) -> list[str]:
    """Compare the company's register with each vendor's registry, both ways."""
    ours = {entry["agent"]: entry for entry in register}
    findings = []
    for vendor, names in vendors.items():
        for name in names:
            if name not in ours:
                findings.append(f"{name}: in {vendor}, not in our register")
            elif not ours[name].get("sponsor"):
                findings.append(f"{name}: in {vendor}, and nobody sponsors it")
    for name, entry in ours.items():
        home = entry["runs_on"]
        if home not in vendors:
            findings.append(f"{name}: on {home}, which no registry covers")
        elif name not in vendors[home]:
            findings.append(
                f"{name}: we say {home}, and {home} does not list it"
            )
    return findings


def contract_breaks(fields: list[str], consumers: dict[str, list[str]]) -> dict:
    """For each consumer, the fields it reads that the new version drops."""
    return {
        name: [field for field in reads if field not in fields]
        for name, reads in consumers.items()
    }
