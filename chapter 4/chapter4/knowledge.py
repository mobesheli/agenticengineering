"""Semantic memory as a tool the agent calls when it decides it needs facts."""

from __future__ import annotations

from agents import RunContextWrapper, function_tool
from pydantic import BaseModel

from chapter4.memory import MemoryContext


class Snippet(BaseModel):
    source: str
    text: str
    score: float


@function_tool
async def search_knowledge(
    ctx: RunContextWrapper[MemoryContext], query: str, top_k: int = 5
) -> list[Snippet]:
    """Search the knowledge base for passages relevant to a question."""
    memory = ctx.context
    query_vector = await memory.embed(query)
    hits = await memory.knowledge.nearest(query_vector, limit=top_k)
    return [Snippet(source=h.source, text=h.text, score=h.score) for h in hits]
