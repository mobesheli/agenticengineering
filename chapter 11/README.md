# Chapter 11 Companion Repo

This folder contains the runnable companion for Chapter 11, *Cutting the Strings: Operating, Evolving, and Letting Go of the Agents You Have Built*.

Start with `Chapter_11_Cutting_the_Strings_Learning_Walkthrough.ipynb`. It follows the maintenance planning agent through a year of configuration drift, model migration, autonomy reviews, memory hygiene, fleet discovery, proposed fixes, sponsor changes, and retirement of a sibling agent.

The default path is deterministic and offline. It needs no API key, makes no model calls, sends no telemetry, and operates entirely on local teaching fixtures. Generated evidence stays beneath the output directory you choose.

## Start Here

Use this order on a first pass:

1. Compare the effective configuration with the pinned release and read the five drift decisions.
2. Rehearse a model outage using an evaluated secondary route.
3. Refuse a promotion above the ceiling or with weak planted-check evidence.
4. Bind the required approvals to one promotion and keep safety work behind approval.
5. Reserve a simulated procurement order under a scoped, expiring mandate.
6. Repair stale pump memory, trace a poisoned source, and erase a record's full local lineage.
7. Reconcile fifteen register entries with two identity registries and test a breaking producer contract.
8. Hold a proposed fix that improves the judge's score without improving independent outcomes.
9. Compare the damage clock with the paging clock and enforce the thirty-minute pause rule.
10. Stop a retirement with a live token, complete it after revocation, and replay the year on one board.

## One-Time Setup

Python 3.11 or later is required. Python 3.12 is recommended.

```bash
cd "chapter 11"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the walkthrough:

```bash
jupyter notebook Chapter_11_Cutting_the_Strings_Learning_Walkthrough.ipynb
```

## Run the Offline Year Review

```bash
python -m chapter11 --output-dir evidence/latest
```

The command emits:

- `board.html`: a self-contained interactive board with a day slider
- `board-state.json`: the selected day's register state and decisions
- `year-replay.json`: all 366 daily snapshots, from launch through day 365
- `memory-hygiene.json` and `memory-lineage.json`: stage results, recall and forgetting scores, quarantine, and erasure
- `fleet-reconciliation.json` and `consumer-contracts.json`: identity gaps and compatible/breaking contract checks
- `fallback-drill.json`, `improvement-gates.json`, and `two-clock-drill.json`: route eligibility, independent review, and response timing
- `retirement-rehearsal.json` and `retirement/`: the refused attempt, completed obituary, retained archive, and archive manifest
- `manifest.json`: SHA-256 hashes for the complete evidence pack

Open `evidence/latest/board.html` in a browser. It works without a server or network connection. Use the slider or arrow keys to inspect any day. Choose a fresh output directory for another run; the command preserves existing evidence by refusing to overwrite a nonempty directory.

Verify the pack:

```bash
python -c 'from pathlib import Path; from chapter11.artifacts import verify_manifest; print(verify_manifest(Path("evidence/latest")))'
```

The manifest detects changed, missing, and additional files. It is an integrity check, not a digital signature or proof that an evaluation was correct.

## Replay a Particular Day

Print a snapshot without writing files:

```bash
python -m chapter11 --day 97 --replay-only
python -m chapter11 --day 140 --replay-only
python -m chapter11 --day 330 --replay-only
```

Or select a snapshot while generating the full review pack:

```bash
python -m chapter11 --day 170 --output-dir evidence/day-170
```

`--day` selects `board-state.json`. The HTML board and the other exercises still cover the whole year. The replay uses the actual promotion and demotion functions: day 97 drops to draft only, day 140 refuses poor review evidence, days 170 and 270 earn rungs two and three, and day 330 blocks renewal after the sponsor leaves. The new sponsor signs on day 365.

Day two follows the code's decision precedence: an effective-configuration mismatch holds first, even when outcome improves. Once the configuration is reconciled, an outcome-only gain proposes a candidate; a cost or speed excursion becomes a budget event. Missing or duplicate signals also hold.

## Optional Live Memory Consolidation

The only model-backed component is the duplicate-memory consolidator. The adapter uses the SDK's [structured-output agent pattern](https://developers.openai.com/api/docs/guides/agents/define-agents). Set `OPENAI_API_KEY` in your environment, then choose an explicit model available to your account:

```bash
python -m chapter11 --live-memory --model YOUR_MODEL_ID \
  --output-dir evidence/live-memory
```

This sends the synthetic duplicate records to the selected model and can incur API charges. The call is limited to two turns, tracing is disabled, and the same source-lineage and score checks apply afterward. It does not change the offline defaults.

For the notebook's optional cell, also set `CHAPTER11_MODEL` and `RUN_LIVE_MEMORY=1` before launching Jupyter. Keep API keys out of notebook cells, data files, and saved outputs.

## Project Map

| File or directory | Purpose |
| --- | --- |
| `Chapter_11_Cutting_the_Strings_Learning_Walkthrough.ipynb` | Guided reader experience, including all eight chapter figures |
| `chapter11/models.py` | Typed configuration, drift, register, evidence, approval, and event contracts |
| `chapter11/drift.py` | Configuration comparison, five decisions, and fallback eligibility |
| `chapter11/autonomy.py` | Empirical pass-to-the-k, promotion gaps, bound approvals, automatic drops, and action routing |
| `chapter11/memory.py` | Four-stage hygiene, independent recall/forgetting gates, rollback, provenance, and local erasure |
| `chapter11/live.py` | Optional SDK consolidator with structured output |
| `chapter11/fleet.py` | Registry reconciliation, consumer contracts, version sunset, and two-pager routing |
| `chapter11/controls.py` | Scoped mandates, independent improvement gate, and two-clock drill |
| `chapter11/retirement.py` | Retirement sequence, credential-residue stop, retained archive, and obituary |
| `chapter11/board.py` | Event replay and portable interactive board |
| `chapter11/evidence.py` | Complete year-review evidence pack |
| `data/` | Small fake register, year events, rules, memories, evidence, identities, and contracts |
| `OPERATOR_CARD.md` | Fifteen operating questions and the sponsor check |
| `POSTMORTEM_TEMPLATE.md` | Review template with four agent-specific fields |
| `assets/` | The eight figures from the Chapter 11 draft |
| `tests/` | Offline control, failure-path, SDK-wiring, replay, CLI, and evidence tests |

## Verify Everything

```bash
pytest -q
ruff check .
ruff format --check .
```

Rebuild and execute the notebook:

```bash
python scripts/build_notebook.py
jupyter nbconvert --to notebook --execute \
  Chapter_11_Cutting_the_Strings_Learning_Walkthrough.ipynb \
  --output /tmp/chapter11-executed.ipynb \
  --ExecutePreprocessor.timeout=180
```

The checked-in notebook has stable cell IDs and no saved outputs. SDK tests replace the runner, so the test suite requires no API key or model access.

## Operating Boundaries

- The maintenance planner's ceiling is three. Safety-critical, lockout, unknown, and irreversible actions stay behind approval. Only risk owners can change the ceiling.
- Promotion requires the declared number of trials, an observation window, planted-check catch rate, cost evidence, incident-free time, current sponsorship, and approvals bound to the exact proposal. Higher rungs add reviewer, drill, and finance requirements.
- Thresholds, roles, ceilings, model names, costs, and timelines are illustrative policy choices for this manufacturer. They do not classify another organization's agents or encode legal deadlines.
- The fake register and approval records are trusted inputs to the exercises. A deployed approval service must authenticate signers, authorize their roles, and persist decisions outside the proposing agent's control.
- Hygiene snapshots support rollback. Erasure removes the transitive lineage from every represented storage tier and snapshot. Real archives, vector stores, and backups need their own adapters and deletion receipts.
- The local mandate ledger uses decimal amounts and idempotency keys. A payment integration needs atomic reservations, persistent revocation, authenticated mandates, currency handling, and reconciliation of in-flight orders.
- The improvement gate never merges a change. Its evaluation report belongs to an independent service; file permissions and service identities must prevent the proposer from changing criteria, held-out cases, logs, or live aliases.
- Retirement changes local fixture state only. It deactivates before archiving, refuses to pass live tokens, preserves required evidence, and removes active memory after the archive is written. Archive retention and eventual deletion require external storage controls.
- The board is a deterministic replay of declared events. Recorded release and attestation events represent previously approved decisions. The drill uses synthetic elapsed times and does not measure a real pager.
