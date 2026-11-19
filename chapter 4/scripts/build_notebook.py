"""Build Chapter_4_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. Every cell that needs a model
drives the SDK runner through its scripted test model, and every cell that needs an
embedding uses the local embedder, so the whole notebook runs without an API key.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_4_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 4: What Agents Remember

This notebook mirrors the chapter. Run the cells in order, from the `Chapter04`
folder. Nothing here needs an API key. The SDK runner, the sessions, the tools,
the MCP server, and the guardrail are all real. Only the model's replies are
scripted, and embeddings come from a small local embedder.

Pinned version: openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
print("openai-agents", version("openai-agents"))
"""
    ),
    md(
        """
## Working memory: What fits in the context window

### Where the past actually lives: Sessions

Two turns through one file-backed session. The scripted model reports how many
earlier items the session placed in front of it on the second turn.
"""
    ),
    code(
        """
from examples import billing_session
from examples.scripted import scripted_billing_model

print(await billing_session.main(scripted_billing_model(), ":memory:"))
"""
    ),
    md(
        """
## Semantic memory: Giving the agent facts it can look up

### The pipeline as a tool the agent reaches for

Index two passages, then search. Every result carries its source.
"""
    ),
    code(
        """
from chapter4.embedding import local_embed
from chapter4.memory import MemoryContext, MemoryScope
from chapter4.stores import EpisodicStore, KnowledgeStore

scope = MemoryScope(org_id="st-marys", user_id="patient-alvarez", agent_id="med-rec")
memory = MemoryContext(scope, local_embed, KnowledgeStore(), EpisodicStore())

for source, text in [
    ("policy/refunds-eu", "Refunds for European orders take five days."),
    ("policy/shipping", "We ship on weekdays."),
]:
    memory.knowledge.add(source, text, await local_embed(text))

query = await local_embed("refunds for European orders")
for hit in await memory.knowledge.nearest(query, limit=2):
    print(f"{hit.score:.2f}  {hit.source:20} {hit.text}")
"""
    ),
    md(
        """
## Episodic memory: Remembering this person, over time

### Store the meaning, not the tape

Redaction runs before anything is embedded or stored.
"""
    ),
    code(
        """
from chapter4.episodes import redact

print(redact("Patient MRN 4471982 reported a severe reaction to amoxicillin."))
print(redact("Dose raised to 40 mg after 180 days."))
"""
    ),
    md(
        """
### Scope is the line between a feature and a breach

One episode is stored for one patient at one hospital. The same search from
another organization, or for another patient, returns nothing.
"""
    ),
    code(
        """
from chapter4.stores import Episode

now = datetime.now(UTC)
stopped = Episode(
    summary="Simvastatin stopped by Dr. Reed.",
    importance=8,
    occurred_at=now - timedelta(days=10),
)
await memory.episodes.append(scope, await local_embed(stopped.summary), stopped)

vector = await local_embed("simvastatin")
other_org = scope.model_copy(update={"org_id": "other-hospital"})
other_user = scope.model_copy(update={"user_id": "patient-brown"})
for label, who in [("same scope", scope), ("other org", other_org), ("other user", other_user)]:
    print(f"{label:11} {len(await memory.episodes.search(who, vector, 5))} result(s)")
"""
    ),
    md(
        """
### Recency, importance, and the art of the gentle discount

Three memories: an old trivial one, a recent one, and an old allergy stored with
`decays=False`. The allergy keeps its full weight.
"""
    ),
    code(
        """
from chapter4.episodes import rank_by_relevance_and_recency, score
from chapter4.stores import EpisodeHit


def hit(text, days_old, similarity, importance=5, decays=True):
    when = now - timedelta(days=days_old)
    episode = Episode(summary=text, importance=importance, occurred_at=when, decays=decays)
    return EpisodeHit(episode, similarity)


hits = [
    hit("Asked about opening hours.", 700, 0.80),
    hit("Asked to move the appointment.", 3, 0.75),
    hit("Severe reaction to amoxicillin.", 700, 0.70, importance=10, decays=False),
]
for h in hits:
    print(f"{score(h, now):.3f}  {h.episode.summary}")
print()
print([e.summary for e in rank_by_relevance_and_recency(hits)])
"""
    ),
    md(
        """
## Procedural memory: Remembering how

### Skills: Procedures you can hold in your hand

The catalog costs one line per skill. The body is loaded only when it is needed.
"""
    ),
    code(
        """
from chapter4.skills import describe_skills, load_skill

print(describe_skills())
print()
print(load_skill("medication-reconciliation"))
"""
    ),
    md(
        """
## The discipline of forgetting

### Deleting when the law says you must

An erasure request takes one record out of retrieval. The record under a legal
hold stays, and both rows still exist until the hard purge.
"""
    ),
    code(
        """
store = EpisodicStore()
morning = Episode(summary="Prefers morning appointments.", importance=3, occurred_at=now)
statin = Episode(summary="Statin decision recorded.", importance=8, occurred_at=now)
await store.append(scope, await local_embed(morning.summary), morning)
await store.append(scope, await local_embed(statin.summary), statin, legal_hold=True)

print("tombstoned:", store.erase("st-marys", "patient-alvarez"))
left = await store.search(scope, await local_embed("appointments statin"), 5)
print("still retrievable:", [h.episode.summary for h in left])
print("rows still stored:", len(store.rows))
"""
    ),
    md(
        """
## Putting it together: A medication reconciliation agent

### One turn, traced

The agent starts the FHIR server as a separate process, reads the record and the
pharmacy fills over MCP, recalls the last reconciliation, checks interactions,
and returns a draft. The scripted model plays the clinician's assistant.
"""
    ),
    code(
        """
from examples import reconcile
from examples.scripted import scripted_clinician_model

seen = {}
model = scripted_clinician_model("Draft for clinician review.", seen)
draft = await reconcile.main(model, local_embed, "sqlite+aiosqlite:///:memory:")

print(draft.status.upper(), "for", draft.patient_ref)
for finding in draft.findings:
    print(" -", finding)
print()
print("recalled episode:", seen["past"][:120])
"""
    ),
    md(
        """
### Where the rules bite, and where it breaks

A note that presents itself as final trips the output guardrail.
"""
    ),
    code(
        """
from agents import OutputGuardrailTripwireTriggered

model = scripted_clinician_model("Final note, signed.", {})
try:
    await reconcile.main(model, local_embed, "sqlite+aiosqlite:///:memory:")
except OutputGuardrailTripwireTriggered:
    print("Guardrail tripped: the agent may only return a draft.")
"""
    ),
]

notebook = nbf.v4.new_notebook(cells=cells)
notebook.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}
NotebookClient(
    notebook, timeout=120, resources={"metadata": {"path": str(ROOT)}}
).execute()
nbf.write(notebook, OUT)
print(f"wrote {OUT.name} with {len(cells)} cells")
