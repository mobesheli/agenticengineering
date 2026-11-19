"""In-memory stores with the same rules the chapter's Postgres schema enforces.

Scope is applied inside the store on every read. Erasure tombstones a record so
it leaves every retrieval path at once, and a record on legal hold is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from chapter4.embedding import cosine

if TYPE_CHECKING:
    from chapter4.memory import MemoryScope


class Episode(BaseModel):
    summary: str
    importance: int
    occurred_at: datetime
    decays: bool = True


class Hit(BaseModel):
    source: str
    text: str
    score: float


@dataclass
class EpisodeHit:
    episode: Episode
    similarity: float


@dataclass
class KnowledgeStore:
    rows: list[tuple[str, str, list[float]]] = field(default_factory=list)

    def add(self, source: str, text: str, vector: list[float]) -> None:
        self.rows.append((source, text, vector))

    async def nearest(self, vector: list[float], limit: int) -> list[Hit]:
        scored = [
            Hit(source=source, text=text, score=round(cosine(vector, stored), 4))
            for source, text, stored in self.rows
        ]
        return sorted(scored, key=lambda hit: hit.score, reverse=True)[:limit]


@dataclass
class StoredEpisode:
    org_id: str
    user_id: str
    episode: Episode
    embedding: list[float]
    valid_to: datetime | None = None
    tombstoned: bool = False
    legal_hold: bool = False


@dataclass
class EpisodicStore:
    rows: list[StoredEpisode] = field(default_factory=list)

    async def append(
        self,
        scope: MemoryScope,
        embedding: list[float],
        episode: Episode,
        legal_hold: bool = False,
    ) -> None:
        self.rows.append(
            StoredEpisode(
                scope.org_id, scope.user_id, episode, embedding, legal_hold=legal_hold
            )
        )

    async def search(
        self, scope: MemoryScope, embedding: list[float], limit: int
    ) -> list[EpisodeHit]:
        visible = [
            row
            for row in self.rows
            if row.org_id == scope.org_id
            and row.user_id == scope.user_id
            and not row.tombstoned
        ]
        hits = [
            EpisodeHit(row.episode, cosine(embedding, row.embedding)) for row in visible
        ]
        return sorted(hits, key=lambda hit: hit.similarity, reverse=True)[:limit]

    def erase(self, org_id: str, user_id: str) -> int:
        """Tombstone a person's episodes. Returns how many left retrieval."""
        now, erased = datetime.now(UTC), 0
        for row in self.rows:
            mine = row.org_id == org_id and row.user_id == user_id
            if mine and not row.legal_hold and not row.tombstoned:
                row.valid_to, row.tombstoned = now, True
                erased += 1
        return erased
