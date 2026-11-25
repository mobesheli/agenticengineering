"""Retiring an agent: deployment run backward, with the same care."""

from __future__ import annotations

from chapter11.systems import Archive, Identity, Register, Traces


class RetirementBlocked(RuntimeError):
    pass


def retire(
    agent: str,
    successor: str,
    today: int,
    register: Register,
    traces: Traces,
    identity: Identity,
    archive: Archive,
) -> dict:
    entry = register.freeze(agent, successor)
    listed = set(entry["consumers"])
    callers = sorted(listed | traces.callers(agent, since=today - 90))
    for caller in callers:
        register.redirect(caller, old=agent, new=successor)
    unmoved = [c for c in callers if not traces.reached(c, successor)]
    if unmoved:
        raise RetirementBlocked(f"not yet served by {successor}: {unmoved}")
    identity.deactivate(agent)
    revoked = identity.revoke_tokens(agent)
    if left := identity.live_tokens(agent):
        raise RetirementBlocked(f"credentials still live: {left}")
    manifest = archive.store(agent, entry, keep_until=entry["keep_until"])
    obituary = {
        "agent": agent,
        "final_bundle": entry["bundle"],
        "successor": successor,
        "callers_moved": callers,
        "unlisted_callers": sorted(set(callers) - listed),
        "tokens_revoked": revoked,
        "archive": manifest,
        "signed_by": entry["sponsor"],
    }
    register.close(agent, obituary)
    return obituary
