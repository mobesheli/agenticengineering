# Chapter 4 Companion Repo

This folder contains the companion learning material for Chapter 4, *What Agents Remember: Memory, Knowledge, and Context*.

Start with `Chapter_4_What_Agents_Remember_Learning_Walkthrough.ipynb`. It follows the chapter section by section and shows what each part is building: working-memory budgets, sessions, semantic retrieval, episodic memory, procedural skills, forgetting controls, memory-security defenses, and the medication reconciliation workflow.

## Start Here

Use this order the first time you open the project:

1. Read the notebook section map.
2. Run the setup cell.
3. Run the live OpenAI endpoint smoke test.
4. Work through the working-memory and OpenAI Agents SDK session examples.
5. Run the semantic retrieval examples with live embeddings.
6. Run the episodic and procedural memory examples.
7. Read the forgetting, poisoning, and audit cells carefully.
8. Finish with the medication reconciliation workflow model.

## One-Time Setup

Python 3.10 or later is required. Python 3.11 is recommended.

```bash
cd "chapter 4"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
```

If you want to open the notebook locally:

```bash
python -m pip install notebook
jupyter notebook
```

## Project Map

- `Chapter_4_What_Agents_Remember_Learning_Walkthrough.ipynb`: guided notebook for readers
- `requirements.txt`: notebook dependencies, including the OpenAI Python SDK, OpenAI Agents SDK, and SQLAlchemy-backed session packages used by the chapter snippets

## What Readers Build

The notebook builds the conceptual and code surface of Chapter 4 in this order:

1. A live OpenAI endpoint smoke test using a mini model.
2. A session-backed OpenAI Agents SDK turn that proves continuity comes from external state.
3. A working-memory budget with anchors, summaries, reserve space, and cache-friendly ordering.
4. A semantic memory path with OpenAI embeddings, chunking, vector search, hybrid retrieval, reranking, and graph lookup.
5. An episodic memory store with write-on-extract, scope filters, recency, importance, and contradiction handling.
6. A procedural memory skill for medication reconciliation.
7. Forgetting controls: eviction, tombstones, redaction, poisoning filters, audit logs, and memory diffs.
8. A medication reconciliation agent shell that uses all four memory tiers.

The notebook requires `OPENAI_API_KEY`. It uses `gpt-4.1-mini` by default, or `OPENAI_MODEL` if the reader sets a different model. The clinical records, audit log, and vector list are application memory stores so readers can inspect the memory plumbing without needing hospital infrastructure.

## Code Reading Guidance

The notebook code is intentionally more commented than production code. Those comments explain why each memory tier, scope filter, retrieval choice, tombstone, redaction step, audit row, and guardrail exists. Readers should run the notebook from top to bottom once before copying any individual snippet into a real project.
