import pytest
from agents import set_tracing_disabled

from chapter4.embedding import local_embed
from chapter4.memory import MemoryContext, MemoryScope
from chapter4.stores import EpisodicStore, KnowledgeStore

set_tracing_disabled(True)


def user_texts(items) -> list[str]:
    if isinstance(items, str):
        return [items]
    out = []
    for item in items:
        if item.get("role") == "user":
            content = item["content"]
            out.append(content if isinstance(content, str) else content[0]["text"])
    return out


@pytest.fixture
def memory() -> MemoryContext:
    scope = MemoryScope(
        org_id="st-marys", user_id="patient-alvarez", agent_id="med-rec"
    )
    return MemoryContext(scope, local_embed, KnowledgeStore(), EpisodicStore())
