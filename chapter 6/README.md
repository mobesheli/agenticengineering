# Chapter 6 Companion Repo

This folder contains the runnable companion for Chapter 6, *Agents That Collaborate: Multi-Agent Systems and A2A*.

Start with `Chapter_6_Agents_That_Collaborate_Learning_Walkthrough.ipynb`. It follows the draft section by section: the three rings of distance, the tool-or-agent decision, signed Agent Cards, A2A task states, the NordBolt embassy, defensive remote-agent consumption, identity and accountability, and the supply-chain sourcing run.

## Start Here

Use this order on a first pass:

1. Run the setup and boundary-decision cells.
2. Build and verify NordBolt's signed Agent Card.
3. Inspect the task lifecycle and run-loop-to-task-state mapping.
4. Start the in-process A2A server and call it through the official A2A client.
5. Send a hostile request and watch border control reject it before the model boundary.
6. Register two approved suppliers and fan quote tasks out in parallel.
7. Compare quotes in plain code, approve one scoped purchase order, and commit it idempotently.
8. Open a supplier circuit breaker and watch the sourcing run preserve the fallback.
9. Finish with the notebook self-check and the chapter-to-notebook map.

## One-Time Setup

Python 3.10 or later is required. Python 3.12 is recommended.

```bash
cd "chapter 6"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the walkthrough:

```bash
jupyter notebook Chapter_6_Agents_That_Collaborate_Learning_Walkthrough.ipynb
```

The notebook's default path is deterministic and offline. Set `OPENAI_API_KEY` only when you reach the clearly marked live Agents SDK cell.

## Project Map

- `Chapter_6_Agents_That_Collaborate_Learning_Walkthrough.ipynb`: guided reader experience
- `chapter6/agent.py`: unchanged NordBolt Agents SDK reasoning core
- `chapter6/card.py`: A2A 1.0 Agent Card, JWS signing, and registry verifier
- `chapter6/executor.py`: run-loop endings mapped to A2A task states
- `chapter6/server.py`: official A2A SDK request handler and Starlette routes
- `chapter6/remote.py`: official client adapter plus timeout, idempotency, and error contracts
- `chapter6/registry.py`: approved counterparties, SLAs, contracts, and circuit breakers
- `chapter6/procurement.py`: quote fan-out, plain-code comparison, approval, and commitment
- `chapter6/audit.py`: request/response hashes and identity at the boundary
- `tests/`: offline unit and protocol integration tests
- `assets/`: the seven figures from the Chapter 6 draft

## Run the Server and Tests

Start the deterministic NordBolt A2A server:

```bash
python -m chapter6.server
```

Its signed card is published at `http://127.0.0.1:9999/.well-known/agent-card.json`, and its JSON-RPC endpoint is `/`.

Run every offline check:

```bash
python -m pytest -q
```

Execute the notebook non-interactively:

```bash
jupyter nbconvert --to notebook --execute \
  Chapter_6_Agents_That_Collaborate_Learning_Walkthrough.ipynb \
  --output /tmp/chapter6-executed.ipynb \
  --ExecutePreprocessor.timeout=180
```

## Deliberate Teaching Boundaries

The signing key in `chapter6/card.py` is intentionally public and uses HS256 so readers can reproduce verification without secret material. It is not a production credential. The chapter's production rule still applies: use an asymmetric organization key in a managed key service, rotate it, and keep accepted verification keys in the reviewed counterparty registry.

The server uses `InMemoryTaskStore` because the notebook needs a zero-configuration loopback. Replace it with durable storage before any caller can depend on a task surviving a deploy.

Most importantly, the remote agent never receives the manufacturer's budget ceiling, target price, fallback list, or working memory. The wire contract carries the bill of materials and delivery constraint only.
