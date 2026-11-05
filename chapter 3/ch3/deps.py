"""The run context: values the model must not control.

Anything the orchestration layer puts in ``RunDeps`` travels to the tools
through ``RunContextWrapper`` and never appears in a model-facing schema.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel


class RunDeps(BaseModel):
    idempotency_key: str   # derived by orchestration, never by the model
    actor_id: str          # the authenticated person behind this run


def derive_idempotency_key(*, run_id: str, customer_id: str, charge_id: str) -> str:
    """Derive a stable key for one refund intent.

    The same run, customer, and charge always produce the same key, across
    crashes and restarts. A different charge produces a different key. The
    model is never asked for this value.
    """
    material = f"refund|{run_id}|{customer_id}|{charge_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
