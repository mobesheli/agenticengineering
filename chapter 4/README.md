# Chapter 4 Companion Repo

This folder contains the companion learning material for Chapter 4, *What Agents Remember: Memory, Knowledge, and Context*.

Start with `Chapter_4_What_Agents_Remember_Learning_Walkthrough.ipynb`. It follows the chapter section by section and shows what each part is building: working-memory budgets, sessions, semantic retrieval, episodic memory, procedural skills, forgetting controls, memory-security defenses, and the medication reconciliation workflow.

## Start Here

Use this order the first time you open the project:

1. Read the notebook section map.
2. Run the setup cell.
3. Work through the working-memory and session examples.
4. Run the semantic retrieval examples.
5. Run the episodic and procedural memory examples.
6. Read the forgetting, poisoning, and audit cells carefully.
7. Finish with the medication reconciliation workflow model.

## One-Time Setup

Python 3.10 or later is required. Python 3.11 is recommended.

```bash
cd "chapter 4"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If you want to open the notebook locally:

```bash
python -m pip install notebook
jupyter notebook
```

## Project Map

- `Chapter_4_What_Agents_Remember_Learning_Walkthrough.ipynb`: guided notebook for readers
- `requirements.txt`: notebook dependencies, including the OpenAI Agents SDK package used by the chapter snippets

## What Readers Build

The notebook builds the conceptual and code surface of Chapter 4 in this order:

1. A session-backed agent turn that proves continuity comes from external state.
2. A working-memory budget with anchors, summaries, reserve space, and cache-friendly ordering.
3. A semantic memory path with chunking, vector search, hybrid retrieval, reranking, and graph lookup.
4. An episodic memory store with write-on-extract, scope filters, recency, importance, and contradiction handling.
5. A procedural memory skill for medication reconciliation.
6. Forgetting controls: eviction, tombstones, redaction, poisoning filters, audit logs, and memory diffs.
7. A medication reconciliation agent shell that uses all four memory tiers.

Most cells run offline with lightweight local teaching doubles. The notebook preserves the real OpenAI Agents SDK import shape so readers can move from the learning examples to SDK-backed code without changing the mental model.

## Code Reading Guidance

The notebook code is intentionally more commented than production code. Those comments explain why each memory tier, scope filter, retrieval choice, tombstone, redaction step, audit row, and guardrail exists. Readers should run the notebook from top to bottom once before copying any individual snippet into a real project.
