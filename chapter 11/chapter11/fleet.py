"""Reconcile accountability with identity and exercise consumer-owned contracts."""

from .models import AgentEntry


def reconcile(
    entries: list[AgentEntry], identities: list[dict], *, day: int
) -> list[dict]:
    register = {entry.agent: entry for entry in entries}
    if len(register) != len(entries):
        raise ValueError("duplicate register entry")
    findings = []
    observed = set()
    for identity in identities:
        agent = identity["agent"]
        observed.add(agent)
        entry = register.get(agent)
        reasons = []
        if entry is None:
            reasons.append("unregistered identity")
        else:
            if not entry.owner or not entry.sponsored(day):
                reasons.append("missing owner or current sponsor attestation")
            if (
                entry.status in ("retired", "deprecated", "suspended")
                and identity["active"]
            ):
                reasons.append("live identity for inactive agent")
        if identity["direct_provider_access"]:
            reasons.append("provider access bypasses the gateway")
        if reasons:
            findings.append(
                {"agent": agent, "registry": identity["registry"], "gaps": reasons}
            )
    for agent, entry in register.items():
        if agent not in observed and entry.status == "live":
            findings.append(
                {
                    "agent": agent,
                    "registry": "not observed",
                    "gaps": [
                        "locate identity in another registry; do not erase the accountability record"
                    ],
                }
            )
    return findings


def contract_gaps(
    contract: dict, response: dict, *, call_version: int, day: int
) -> list[str]:
    accepted = {contract["version"]}
    previous = contract["previous"]
    if previous["compatibility_mode"] and day < previous["sunset_day"]:
        accepted.add(previous["version"])
    if call_version not in accepted:
        return ["contract version is unsupported or its sunset has passed"]
    gaps = []
    for consumer in contract["consumers"]:
        for field, kind in consumer["requires"].items():
            value = response.get(field)
            valid = (
                isinstance(value, str)
                if kind == "string"
                else type(value) is int and value >= 0
                if kind == "nonnegative_integer"
                else False
            )
            if not valid:
                gaps.append(f"{consumer['agent']}: {field} must be {kind}")
    return gaps


def pager(entry: AgentEntry, incident: str) -> str:
    if incident == "infrastructure":
        return "platform-rotation"
    if incident == "behavior":
        return entry.owner
    raise ValueError("incident must be infrastructure or behavior")
