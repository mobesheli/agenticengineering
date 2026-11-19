"""Two embedders with one signature: the provider's, and a local one for tests."""

from __future__ import annotations

import hashlib
import math
import re

from openai import AsyncOpenAI

from chapter4.models import MODELS


async def openai_embed(text: str) -> list[float]:
    """Embed text with the model named in the registry. Needs OPENAI_API_KEY."""
    response = await AsyncOpenAI().embeddings.create(model=MODELS.embedding, input=text)
    return response.data[0].embedding


async def local_embed(text: str, size: int = 256) -> list[float]:
    """A deterministic bag-of-words embedding. Good enough to test the plumbing."""
    vector = [0.0] * size
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % size] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (
        (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0
    )
