"""The memory an agent run is allowed to touch.

Tools read the scope from here. The model never supplies it, so a persuasive
prompt cannot point a search at somebody else's records.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from chapter4.stores import EpisodicStore, KnowledgeStore

Embedder = Callable[[str], Awaitable[list[float]]]


class MemoryScope(BaseModel):
    org_id: str
    user_id: str
    agent_id: str
    session_id: str | None = None


@dataclass
class MemoryContext:
    scope: MemoryScope
    embed: Embedder
    knowledge: KnowledgeStore
    episodes: EpisodicStore
