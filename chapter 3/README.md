# Chapter 3 Companion Repo

This folder contains the companion learning material for Chapter 3, *Giving Agents Hands: Tools, Function Calling, and MCP*.

Start with `Chapter_3_Giving_Agents_Hands_Learning_Walkthrough.ipynb`. It follows the chapter section by section and shows what each part is building: tool interfaces, agent-readable errors, idempotent write tools, approval gates, MCP server wiring, and the financial services audit-prep workflow.

## Start Here

Use this order the first time you open the project:

1. Read the notebook section map.
2. Run the setup cell.
3. Work through the tool-design examples.
4. Run the side-effect boundary examples.
5. Read the MCP cells before using a real MCP server.
6. Finish with the audit-prep workflow model.

## One-Time Setup

Python 3.10 or later is required. Python 3.11 is recommended.

```bash
cd "chapter 3"
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

- `Chapter_3_Giving_Agents_Hands_Learning_Walkthrough.ipynb`: guided notebook for readers
- `assets/figure_3_1_stochastic_loop.png`: chapter figure for retry failure patterns
- `assets/figure_3_2_mcp_topology.png`: chapter figure for MCP host/client/server topology
- `assets/figure_3_3_audit_prep_architecture.png`: chapter figure for the audit-prep agent architecture
- `requirements.txt`: notebook dependencies and optional SDK packages used by the chapter snippets

## What Readers Build

The notebook builds the conceptual and code surface of Chapter 3 in this order:

1. A model of tool calls as Python functions plus typed descriptions.
2. Intent-shaped tools for purchase-order changes.
3. A structured error response the agent can act on.
4. An idempotency-aware refund tool.
5. A human approval gate.
6. A small MCP server shape and MCP client wiring.
7. A journal schema for auditable tool calls.
8. The data models and agent shell for a financial services audit-prep agent.

Most cells run offline with lightweight local mocks. The MCP cells are written as teaching code first; replace the mock server and URLs with your real infrastructure before using them outside the notebook.

## Code Reading Guidance

The notebook code is intentionally more commented than production code. Those comments explain why each field, schema, idempotency key, approval gate, and mock object exists. Readers should run the notebook from top to bottom once before copying any individual snippet into a real project.
