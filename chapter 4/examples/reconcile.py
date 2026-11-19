"""Run the medication reconciliation agent against the sample FHIR server.

python -m examples.reconcile              # needs OPENAI_API_KEY
python -m examples.reconcile --scripted   # no key: scripted model, local embedder
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from agents import Runner
from agents.mcp import MCPServerStdio
from agents.models.interface import Model

from chapter4.embedding import openai_embed
from chapter4.memory import Embedder, MemoryContext, MemoryScope
from chapter4.models import MODELS
from chapter4.reconciliation import ReconciliationDraft, build_med_rec_agent
from chapter4.sessions import database_session
from chapter4.stores import Episode, EpisodicStore, KnowledgeStore

INTERACTIONS = [
    (
        "interactions/anticoagulant-nsaid",
        "Apixaban with ibuprofen or another NSAID raises bleeding risk. Avoid or monitor.",
    ),
    (
        "interactions/statin-macrolide",
        "Simvastatin with clarithromycin raises the risk of muscle injury.",
    ),
    (
        "guidance/statin-duplicate",
        "Two statins together add risk without benefit. Keep one.",
    ),
]
REQUEST = "Reconcile the medications for patient-alvarez before the two o'clock. He says his cardiologist changed something."


async def seeded_memory(embed: Embedder) -> MemoryContext:
    scope = MemoryScope(
        org_id="st-marys", user_id="patient-alvarez", agent_id="med-rec"
    )
    knowledge, episodes = KnowledgeStore(), EpisodicStore()
    for source, text in INTERACTIONS:
        knowledge.add(source, text, await embed(text))
    last_visit = Episode(
        summary="Duplicate statin resolved. Simvastatin stopped by Dr. Reed. Atorvastatin continues.",
        importance=8,
        occurred_at=datetime.now(UTC) - timedelta(days=90),
    )
    await episodes.append(
        scope, await embed(last_visit.summary), last_visit, legal_hold=True
    )
    return MemoryContext(
        scope=scope, embed=embed, knowledge=knowledge, episodes=episodes
    )


async def main(
    model: str | Model = MODELS.mid,
    embed: Embedder = openai_embed,
    db_url: str = "sqlite+aiosqlite:///encounters.db",
) -> ReconciliationDraft:
    memory = await seeded_memory(embed)
    session = database_session("encounter-7731", db_url)
    params = {"command": sys.executable, "args": ["-m", "chapter4.fhir_server"]}
    async with MCPServerStdio(params=params, cache_tools_list=True) as fhir_server:
        agent = build_med_rec_agent(fhir_server, model)
        result = await Runner.run(agent, REQUEST, session=session, context=memory)
    return result.final_output


if __name__ == "__main__":
    if "--scripted" in sys.argv:
        from chapter4.embedding import local_embed
        from examples.scripted import scripted_clinician_model

        model = scripted_clinician_model("Draft for clinician review.", {})
        draft = asyncio.run(main(model, local_embed, "sqlite+aiosqlite:///:memory:"))
    else:
        draft = asyncio.run(main())
    print(draft.status.upper(), "for", draft.patient_ref)
    for finding in draft.findings:
        print(" -", finding)
