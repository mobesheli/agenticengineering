"""Sending a fixed share of traffic to a candidate model, the same way every time."""

import hashlib

from chapter5.models import MODELS


def pick_frontier_model(request_id: str, canary_share: float = 0.05) -> str:
    digest = hashlib.sha256(request_id.encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") / 2**32
    return MODELS.frontier_canary if bucket < canary_share else MODELS.frontier
