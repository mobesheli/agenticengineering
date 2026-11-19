"""Episodic memory: write distilled episodes, read them back ranked."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from agents import Agent, RunContextWrapper, Runner, function_tool
from agents.models.interface import Model
from pydantic import BaseModel

from chapter4.memory import MemoryContext
from chapter4.models import MODELS
from chapter4.stores import Episode, EpisodeHit

EXTRACTION_GUIDE = """
Read the conversation and return only what is worth remembering later: a
decision, a stated preference, a problem left open, or a specific event. Write
each as one self-contained sentence. Score importance from 1 to 10, where 10
would change what a careful colleague does next. Set decays to false for
anything that stays true until someone corrects it, such as an allergy.
Refer to the person by role, such as the patient or the customer, never by
name. Return an empty list when nothing qualifies.
""".strip()

IDENTIFIER = re.compile(
    r"\b(?:MRN|NHS|SSN)[ :#-]*\d[\d -]{4,}\d\b|\b\d{3}-\d{2}-\d{4}\b"
)


class Observation(BaseModel):
    summary: str
    importance: int
    decays: bool


class Extraction(BaseModel):
    episodes: list[Observation]


def redact(text: str) -> str:
    """Remove direct identifiers before anything is embedded or stored."""
    return IDENTIFIER.sub("[identifier removed]", text)


async def extract_episodes(
    conversation: str, occurred_at: datetime, model: str | Model = MODELS.fast
) -> list[Episode]:
    """Ask the model what is worth keeping. The caller supplies the time."""
    extractor = Agent(
        name="episode-extractor",
        model=model,
        instructions=EXTRACTION_GUIDE,
        output_type=Extraction,
    )
    run = await Runner.run(extractor, conversation)
    return [
        Episode(occurred_at=occurred_at, **observation.model_dump())
        for observation in run.final_output.episodes
    ]


async def remember(
    conversation: str, memory: MemoryContext, model: str | Model = MODELS.fast
) -> int:
    episodes = await extract_episodes(conversation, datetime.now(UTC), model)
    for episode in episodes:
        episode.summary = redact(episode.summary)
        vector = await memory.embed(episode.summary)
        await memory.episodes.append(memory.scope, vector, episode)
    return len(episodes)


def score(hit: EpisodeHit, now: datetime, half_life_days: float = 90.0) -> float:
    age_days = max((now - hit.episode.occurred_at).days, 0)
    decay = 0.5 ** (age_days / half_life_days) if hit.episode.decays else 1.0
    return hit.similarity * decay * (0.5 + hit.episode.importance / 20)


def rank_by_relevance_and_recency(hits: list[EpisodeHit]) -> list[Episode]:
    now = datetime.now(UTC)
    ranked = sorted(hits, key=lambda hit: score(hit, now), reverse=True)
    return [hit.episode for hit in ranked]


@function_tool
async def recall_episodes(
    ctx: RunContextWrapper[MemoryContext], situation: str, top_k: int = 3
) -> list[Episode]:
    """Recall past episodes with this person that bear on the current situation."""
    memory = ctx.context
    vector = await memory.embed(situation)
    candidates = await memory.episodes.search(memory.scope, vector, limit=top_k * 5)
    return rank_by_relevance_and_recency(candidates)[:top_k]
