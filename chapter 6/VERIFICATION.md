# Chapter 6 companion code: verification record

Date of the run: 2026-11-11. Interpreter: Python 3.13.18 in a fresh virtual
environment built from `requirements.txt`.

## Versions

| Package | Version |
| --- | --- |
| a2a-sdk | 1.3.0, with the `http-server` and `signing` extras |
| openai-agents | 0.24.0 |
| openai | 3.49.0 |
| pydantic | 2.14.3 |
| httpx | 0.28.1 |
| starlette / uvicorn | 1.10.0 / 0.54.0 |
| PyJWT / cryptography | 2.15.1 / 50.0.2 |
| pytest / pytest-asyncio | 9.0.3 / 1.4.1.post1 |
| nbclient / nbformat | 0.11.0 / 5.11.1 |

## Commands run

All commands from this folder, with `python` being the virtual environment's interpreter.

```bash
python -m pytest -q                      # 44 passed
python -m examples.show_card
python -m examples.quote_roundtrip
python -m drills.hostile_request
python -m drills.untrusted_card
python -m drills.parked_task
python -m drills.retry_same_message
python -m drills.supplier_down
python -m drills.three_day_silence
python -m drills.sourcing_run
python scripts/capture_outputs.py        # runs the nine scripts above, writes outputs/
python scripts/build_notebook.py         # builds and executes the notebook, 28 cells
```

Every command exited cleanly with nothing on standard error.

## What the runs exercise

Each example and drill starts two supplier agents as A2A servers built with the
SDK's `DefaultRequestHandler`, mounted on Starlette, and reached through
`httpx` over an in-process transport. The buyer side uses the SDK's
`A2ACardResolver` and `create_client`. Cards are signed with ES256 and verified
through the SDK's signature verifier. The model is the Agents SDK's
`ScriptedModel`, driven by the real `Runner`.

## Listings and console blocks

A script checks every Python listing in the chapter manuscript against this
folder, ignoring docstrings and whitespace, and every console block against
`outputs/`. Result: 28 blocks, 0 missing.

## Live run against a real model

Run on 2026-11-11 with `python -m chapter6.server` on 127.0.0.1:9999 and the
mid-tier model from the registry, called over a real socket through the A2A
client.

| Check | Result |
| --- | --- |
| `python -m examples.live_quote` | A quote of 3.13 GBP, 28 days, valid for 14 days, in about six seconds |
| Same request repeated in the same sourcing case | The stored quote, with no second model run |
| Part description carrying an instruction | Rejected at the border, model not called |
| Bill of materials without a drawing revision | `input-required`, then a quote on the same task after the answer |
| Order committed, then retried with the same order number | One confirmation, returned twice |
| Order stretched beyond its approval | Refused in the buyer's own code, nothing sent |
| Six direct runs of the quoting agent | Both tools called every time, and every term identical to the pricing tool's output |
| Three hostile part descriptions sent straight to the agent, border bypassed | The quoted terms were unchanged in all three |

The live run found three defects that the scripted runs could not, all fixed:
the pricing tool did not return a lead time, validity date, or quote reference,
so a real model made them up; the live example's HTTP client timed out before
the model answered; and the border's instruction screen missed the phrasing
"ignore your previous instructions".

## What was not exercised

- Real network transport between two machines. The drills use an in-process
  transport. The live path uses a local socket.
- OAuth token validation and rate limiting. The card declares the scheme. The
  companion server does not enforce it, and the chapter says so.
- Database-backed task and notification stores. The examples use the SDK's
  in-memory stores.
- The second supplier and the webhook handler against a real model. Both ran
  with the scripted model only.

## Things that vary between runs

- Dates are computed from the day of the run, so `valid until`, the approval
  expiry, and the request and response hashes change from day to day.
- In `drills.sourcing_run`, the two quote lines of the audit trail can appear in
  either order, because the two requests run in parallel.
