# Chapter 4 companion code: verification record

Date of the run: 2026-11-19. Interpreter: Python 3.13.18 in a virtual environment built from `requirements.txt`.

## Versions

| Package | Version |
| --- | --- |
| openai-agents | 0.24.0, with the `sqlalchemy` extra |
| openai | 3.55.0 |
| mcp | 2.3.0 |
| pydantic | 2.14.3 |
| SQLAlchemy / aiosqlite | 2.1.9 / 0.22.1 |
| pytest / pytest-asyncio | 9.0.3 / 1.5.0 |
| nbclient / nbformat | 0.11.0 / 5.11.1 |

## Commands run

All commands from this folder, with `python` being the virtual environment's interpreter.

```bash
python -m pytest -q                              # 21 passed
python -m examples.billing_session --scripted
python -m examples.reconcile --scripted
python -m examples.billing_session               # live model
python -m examples.reconcile                     # live model and live embeddings
python scripts/build_notebook.py                 # builds and executes the notebook, 20 cells
```

Every command exited cleanly. The printed results are in `outputs/`.

## What the scripted runs exercise

- Sessions: a real `SQLiteSession` and a real `SQLAlchemySession` over SQLite. The test checks that the second turn receives the first turn's message.
- Semantic memory: the `search_knowledge` function tool, called by the runner, returning passages with their source.
- Episodic memory: extraction through a structured output type, redaction before storage, the time stamped by the application, scope taken from the run context, isolation between organizations and between users, decay ranking with a memory that does not decay, and a check that the recall tool's schema offers the model no scope argument.
- Forgetting: an erasure that tombstones one record and leaves the record under a legal hold.
- Procedural memory: the skill catalog and loader.
- The reconciliation agent: the FHIR server started as a separate process and reached over MCP stdio, both read tools called, the prior episode recalled, the interaction base searched, a `ReconciliationDraft` returned, and the output guardrail tripping on a note that asserts a sign-off.

## What the live runs showed

Models: `gpt-6.1-terra` for the agents, `gpt-6-luna` for extraction, `text-embedding-3-small` for embeddings.

- Billing session, 10 runs: every reply to "I got cut off. Where were we?" recalled the March double charge. The same message with no session got "I don't have the earlier conversation."
- Extraction, 1 run on a clinic conversation: two episodes kept (the amoxicillin reaction with importance 10 and `decays` false, and the statin decision), the parking question dropped, the patient referred to by role, and both stamped with the current time.
- Knowledge search, 1 run: the model called `search_knowledge` and answered with the passage and its source.
- Reconciliation, 9 runs: every run called `get_active_medications`, `get_pharmacy_fills`, `recall_episodes`, and `search_interactions`, flagged apixaban with ibuprofen, identified apixaban as the recent cardiology order, did not re-flag the stopped simvastatin, and returned a draft that passed the guardrail.
- Follow-up turn, 2 runs: when the clinician stated a decision, the model called `redact_and_remember`, and the episode was stored under the patient's scope with a legal hold.
- Persistence: the encounter was read back from the database file through a new session object.
- Tokens for one reconciliation turn: about 2,500 input across three model calls, about 500 output, none cached. The prompts are below the size the provider caches.

## Listings

Every code listing in the chapter was compared with these files, line for line and with the same indentation, using the Word file itself as the source. All 14 listings match.

## Not run

- The SQL in `sql/`. It is written for PostgreSQL with `pgvector` and was not executed against a database.
