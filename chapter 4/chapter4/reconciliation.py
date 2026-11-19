"""The medication reconciliation agent: all four kinds of memory in one run."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    function_tool,
    output_guardrail,
)
from agents.mcp import MCPServer
from agents.models.interface import Model
from pydantic import BaseModel

from chapter4.episodes import recall_episodes, redact
from chapter4.knowledge import Snippet
from chapter4.memory import MemoryContext
from chapter4.models import MODELS
from chapter4.skills import load_skill
from chapter4.stores import Episode


class ReconciliationDraft(BaseModel):
    status: Literal["draft"]
    patient_ref: str
    findings: list[str]
    note: str


@function_tool
async def search_interactions(
    ctx: RunContextWrapper[MemoryContext], drugs: list[str]
) -> list[Snippet]:
    """Search the drug-interaction knowledge base for a set of drug names."""
    memory = ctx.context
    vector = await memory.embed(" ".join(drugs))
    hits = await memory.knowledge.nearest(vector, limit=3)
    return [Snippet(source=h.source, text=h.text, score=h.score) for h in hits]


@function_tool
async def redact_and_remember(
    ctx: RunContextWrapper[MemoryContext], summary: str, importance: int
) -> str:
    """Store one reconciliation decision for this patient, identifiers removed."""
    memory = ctx.context
    episode = Episode(
        summary=redact(summary), importance=importance, occurred_at=datetime.now(UTC)
    )
    vector = await memory.embed(episode.summary)
    await memory.episodes.append(memory.scope, vector, episode, legal_hold=True)
    return "stored"


SIGN_OFF = re.compile(
    r"\b(?:electronically signed|signed(?: off)? by|finalized by|final note)\b",
    re.IGNORECASE,
)
NOT_YET = re.compile(
    r"\b(?:not|no|never|cannot|unsigned|pending|awaiting|before|until|must|should"
    r"|needs?|requires?|to be)\b|n't",
    re.IGNORECASE,
)


def claims_sign_off(note: str) -> bool:
    """True when a sentence asserts a sign-off, not when it only mentions one."""
    sentences = re.split(r"[.;!?\n]+", note)
    return any(SIGN_OFF.search(s) and not NOT_YET.search(s) for s in sentences)


@output_guardrail
async def never_finalize_clinical_note(
    ctx: RunContextWrapper[MemoryContext], agent: Agent, output: ReconciliationDraft
) -> GuardrailFunctionOutput:
    return GuardrailFunctionOutput(
        output_info=output.status, tripwire_triggered=claims_sign_off(output.note)
    )


def build_med_rec_agent(
    fhir_server: MCPServer, model: str | Model = MODELS.mid
) -> Agent[MemoryContext]:
    return Agent(
        name="med-reconciliation",
        model=model,
        instructions=load_skill("medication-reconciliation"),
        tools=[search_interactions, recall_episodes, redact_and_remember],
        mcp_servers=[fhir_server],
        output_type=ReconciliationDraft,
        output_guardrails=[never_finalize_clinical_note],
    )
