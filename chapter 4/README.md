# Chapter 4: What Agents Remember

Companion code for Chapter 4 of *Agentic AI Engineering*, *What Agents Remember: Memory, Knowledge, and Context*.

The chapter covers four kinds of agent memory and the discipline of forgetting. The code implements each one against the real OpenAI Agents SDK: sessions for working memory, a search tool for semantic memory, a scoped episode store for episodic memory, a skill folder for procedural memory, and a medication reconciliation agent that uses all four.

The tests, the walkthrough notebook, and the `--scripted` mode of both examples need no API key. The SDK runner, the sessions, the tools, the MCP server, and the output guardrail are all real. Only the model's replies are scripted, and embeddings come from a small local embedder. Without the flag, the two examples call a real model and need `OPENAI_API_KEY`.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`openai-agents` is pinned to 0.24.0 and installed with its `sqlalchemy` extra. `aiosqlite` lets the database-backed session run on a local SQLite file, so no database server is needed.

## Run and verify

Run every command from this folder.

| Command | What it exercises | What you should see |
| --- | --- | --- |
| `python -m pytest -q` | The test suite | 21 tests passing |
| `python -m examples.billing_session --scripted` | Two turns through one session | A reply that quotes the first turn back |
| `python -m examples.reconcile --scripted` | One reconciliation turn through all four kinds of memory | A draft for `patient-alvarez` with two findings |
| `python -m examples.billing_session` | The same session with a real model. Needs `OPENAI_API_KEY` | A reply that recalls the March double charge |
| `python -m examples.reconcile` | The same turn with a real model and real embeddings. Needs `OPENAI_API_KEY` | A draft that flags apixaban with ibuprofen and does not re-flag the stopped statin |

The `outputs/` folder holds what all four commands printed when the chapter was written. A live model words its reply differently on every run, so expect the same substance and different sentences.

`Chapter_4_Learning_Walkthrough.ipynb` runs the chapter's ideas in order: sessions, knowledge search, redaction, scope, decay ranking, skills, erasure with a legal hold, the full reconciliation turn, and the guardrail. `python scripts/build_notebook.py` rebuilds and executes it.

## Where things are

| Path | What it holds | Chapter section |
| --- | --- | --- |
| `chapter4/models.py` | The only place model names appear | Technical requirements |
| `chapter4/sessions.py`, `examples/billing_session.py` | File-backed and database-backed sessions | Where the past actually lives: Sessions |
| `chapter4/knowledge.py` | `search_knowledge`, a search tool that returns passages with their source | The pipeline as a tool the agent reaches for |
| `chapter4/memory.py` | `MemoryScope` and the run context that carries it | Scope is the line between a feature and a breach |
| `chapter4/episodes.py` | Extraction, redaction, `remember`, decay scoring, `recall_episodes` | Episodic memory |
| `chapter4/stores.py` | In-memory knowledge and episode stores with scope filtering, tombstones, and legal hold | Episodic memory, The discipline of forgetting |
| `chapter4/skills.py`, `skills/` | Skill catalog and loader, and the reconciliation skill | Skills: Procedures you can hold in your hand |
| `chapter4/fhir_server.py`, `data/` | A read-only MCP server with two tools and one sample patient | The architecture, on top of what you already have |
| `chapter4/reconciliation.py`, `examples/reconcile.py` | The agent, its draft-only output type, and its guardrail | Putting it together |
| `sql/schema.sql`, `sql/erasure.sql` | The episode table with row-level security, and the soft-delete statement | The data, where the compliance actually lives |
| `examples/scripted.py` | The scripted model replies used by the tests, the notebook, and `--scripted` | |

## What is simplified

The stores in `chapter4/stores.py` keep their rows in memory so the code runs anywhere. They apply the same rules as the SQL in `sql/`: every read filters on organization and user, an erasure tombstones rows without deleting them, and a row under a legal hold is left alone. The SQL is written for PostgreSQL with the `pgvector` extension and is not executed by the tests.

The local embedder in `chapter4/embedding.py` hashes words into a vector. It is deterministic and good enough to make the tests meaningful. It is not a substitute for a real embedding model.

The sample patient in `data/alvarez.json` is invented. The FHIR server returns simplified records, not full FHIR resources.

The redaction function removes a few identifier patterns to show where redaction belongs in the write path. A production system needs a proper entity-recognition and redaction service.

The output guardrail looks for a sentence that asserts a sign-off and ignores sentences that deny one. It is a check on prose and can be worded around. The two controls that carry the draft-only rule are the read-only FHIR server and the output type.
