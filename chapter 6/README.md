# Chapter 6: Agents That Collaborate

Companion code for Chapter 6 of *Agentic AI Engineering*, *Agents That Collaborate: Multi-Agent Systems and A2A*.

The chapter is about working with agents you do not own. The code shows both sides of that boundary: a supplier that exposes a quoting agent over A2A, and a manufacturer that finds, calls, and survives that agent.

Nothing here needs an API key. Two supplier agents run as real A2A servers inside one process, with signed Agent Cards and task endpoints, and the buyer calls them through the official A2A client. Only the model is replaced, by the OpenAI Agents SDK's scripted test model, so every run behaves the same way.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The two libraries the chapter depends on are pinned: `a2a-sdk` 1.3.0, with its `http-server` and `signing` extras, and `openai-agents` 0.24.0.

## Run and verify

Run every command from this folder.

| Command | What it exercises | What you should see |
| --- | --- | --- |
| `python -m examples.show_card` | Building, signing, and verifying an Agent Card | A valid signature, a fingerprint, and a tampered card refused |
| `python -m examples.quote_roundtrip` | A verified quote task and its audit record | A quote of 3.13 GBP and a `completed` task in the audit lines |
| `python -m drills.hostile_request` | Border control | `supplier_rejected` with zero model calls |
| `python -m drills.untrusted_card` | Key rotation, an unknown key, and a changed card | One quote and two `supplier_untrusted_card` results |
| `python -m drills.parked_task` | The `input-required` state | A question, then a quote on the same task |
| `python -m drills.retry_same_message` | Idempotent commitment | One confirmation twice, one refusal, one order |
| `python -m drills.supplier_down` | Timeouts and the circuit breaker | The breaker opening on the third failure, and a quote from the fallback |
| `python -m drills.three_day_silence` | The webhook handler | Six queued notifications, a duplicate ignored, and a wrong token refused |
| `python -m drills.sourcing_run` | The whole sourcing round | Two quotes, one approved order, and four audit lines |
| `python -m pytest -q` | The test suite | 44 tests passing |

The `outputs/` folder holds what each command printed when the chapter was written. `python scripts/capture_outputs.py` regenerates it. Dates in the output are computed from the day you run the code, so dates and the hashes derived from them will differ from the saved files. In the sourcing run, the two quote lines of the audit trail can appear in either order, because the requests run in parallel.

`Chapter_6_Learning_Walkthrough.ipynb` runs the same examples and drills in chapter order. `python scripts/build_notebook.py` rebuilds and executes it.

## Running against a real model

```bash
export OPENAI_API_KEY=...            # your own key
python -m chapter6.server            # terminal one: NordBolt on 127.0.0.1:9999
python -m examples.live_quote        # terminal two: the buyer
```

This is the same client path the drills use. The card is fetched over a real socket and the quote is written by a model. Expect a few seconds for the answer. The terms of the quote come from the pricing tool, so the price, lead time, and validity date are the same on every run, and the reference changes with the date.

## Layout

| Path | What it holds |
| --- | --- |
| `chapter6/models.py` | The model registry. Model names appear nowhere else |
| `chapter6/contracts.py` | The typed contracts both sides share: bill of materials, quote, purchase order, approval, and the result types |
| `chapter6/agent.py` | NordBolt's quoting agent and its two private tools |
| `chapter6/card.py`, `keys.py` | Building, signing, and fingerprinting the Agent Card |
| `chapter6/border.py` | Border control: the checks that run before any model sees a request |
| `chapter6/ledger.py` | The supplier's ledger, including idempotent replay |
| `chapter6/executor.py` | The bridge from the Agents SDK run loop to the A2A task lifecycle |
| `chapter6/server.py` | The A2A server |
| `chapter6/registry.py` | The counterparty registry: trust records, signing keys, circuit breakers |
| `chapter6/remote.py` | Calling a remote agent defensively |
| `chapter6/tools.py` | The same call exposed to a model as a function tool |
| `chapter6/procurement.py` | The sourcing workflow: fan out, compare, propose, commit |
| `chapter6/webhook.py` | The push notification handler |
| `chapter6/audit.py` | The boundary audit log |
| `chapter6/neighborhood.py`, `sample.py` | The two fictional suppliers and the sample order used by the examples |
| `examples/`, `drills/` | The runnable scripts from the chapter |
| `tests/` | The test suite |
| `demo_keys/` | Signing keys for the examples |

## A warning about the demo keys

The key pairs in `demo_keys/` are published so that the examples run. Never use them, or any key stored in a repository, for a real agent. A production signing key belongs in a key management system.

The companion server also leaves out two things a production deployment needs: a gateway that validates the caller's OAuth token and limits request rates, and database-backed task and notification stores. The chapter explains both.
