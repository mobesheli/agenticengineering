# Chapter 8 Companion Repo

This folder contains the runnable companion for Chapter 8, *Keeping Agents in Line: Security, Guardrails, and Governance*.

Start with `Chapter_8_Keeping_Agents_in_Line_Learning_Walkthrough.ipynb`. It follows the draft section by section: the four incident classes, the Rule of Two, prompt-injection-resistant architecture, tool guardrails, action-bound approvals, temporal policy, least privilege, trace redaction, bounded autonomy, tamper-evident decisions, responsible AI checks, and the secured medication-reconciliation pattern.

## Start Here

Use this order on a first pass:

1. Map the four incident classes onto the five-subsystem architecture.
2. Apply the Rule of Two to the reconciliation workflow.
3. Load a hostile clinical note and confirm it cannot add a tool or reach the write path.
4. Exercise the versioned tool catalog and cross-patient guardrail.
5. Bind a clinician approval to one proposal hash and enforce its role and expiry.
6. Run the hourly write policy, trace redactor, canary check, and subject-scoped memory store.
7. Trip the stop button and verify the next action is refused outside the agent process.
8. Complete one approved reconciliation and verify both the hash chain and FHIR `AuditEvent`.
9. Emit the security evidence pack and verify its manifest.

## One-Time Setup

Python 3.11 or later is required. Python 3.12 is recommended.

```bash
cd "chapter 8"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the walkthrough:

```bash
jupyter notebook Chapter_8_Keeping_Agents_in_Line_Learning_Walkthrough.ipynb
```

The default route is deterministic and offline. The optional live read-phase adapter uses only `OPENAI_API_KEY` from your current environment. The project does not create, copy, or persist credentials.

## Project Map

- `Chapter_8_Keeping_Agents_in_Line_Learning_Walkthrough.ipynb`: guided reader experience
- `chapter8/threats.py`: four incident classes, Rule of Two, and consequence-based autonomy
- `chapter8/identity.py`: patient-scoped, short-lived session context and phase scopes
- `chapter8/catalog.py`: versioned tool catalog plus the Agents SDK tool-input guardrail
- `chapter8/approvals.py`: stable action hashes, role and expiry checks, and approval-request linting
- `chapter8/policy.py`: append-only event history, write budgets, and temporal policy
- `chapter8/governance.py`: trace redaction, canary detection, and subject-scoped memory deletion
- `chapter8/audit.py`: hash-chained decision records and FHIR `AuditEvent` output
- `chapter8/reconciliation.py`: quarantined read phase and deterministic clinician write path
- `chapter8/registry.py`: externally enforced agent enablement and stop control
- `chapter8/runtime.py`: complete offline security harness
- `chapter8/live.py`: optional OpenAI Agents SDK read-phase adapter
- `chapter8/responsible.py`: fairness tripwire and first-turn disclosure
- `chapter8/evidence.py`: review-ready security evidence artifacts and hashed manifest
- `data/fixtures/`: synthetic patient records, including an indirect-injection case
- `data/catalog/`: reviewed tool permissions and consequence tiers
- `data/policies/`: versioned temporal write policy
- `tests/`: offline unit, integration, privacy, SDK-wiring, and evidence tests
- `assets/`: the six figures from the Chapter 8 draft

## Run the Harness

Run the complete offline healthcare pattern and emit an evidence folder:

```bash
python -m chapter8 --fixture hostile_note --evidence-dir evidence/latest
```

The hostile note remains confined to the read phase. The command creates a typed proposal, records a clinician approval, executes the deterministic write path, verifies the audit chain, tests the stop control, and prints a redacted report.

Build the live read-phase agent without calling a model:

```bash
python -m chapter8 --show-live-wiring
```

Run the live read phase only when you deliberately opt in with your own environment credential:

```bash
test -n "$OPENAI_API_KEY"
python -m chapter8 --live --fixture clean
```

Run every offline check:

```bash
pytest -q
```

Rebuild and execute the checked-in notebook:

```bash
python scripts/build_notebook.py
jupyter nbconvert --to notebook --execute \
  Chapter_8_Keeping_Agents_in_Line_Learning_Walkthrough.ipynb \
  --output /tmp/chapter8-executed.ipynb \
  --ExecutePreprocessor.timeout=180
```

## Security Boundaries

- The fixtures are synthetic and contain no real patient information.
- No secret, access token, refresh token, or authorization header is checked into this folder.
- The read phase has no write tool and no write scope.
- Clinical note text is reduced to hashes and detector signals before the typed proposal crosses the trust boundary.
- The write path runs only after a named clinician grants a fresh approval for the exact proposal hash.
- Tool permissions come from the reviewed catalog, never from a prompt or shared credential.
- Policy and audit records are written outside the model path, and the audit chain is append-only through its public interface.
- The stop control disables the catalog entry at the gateway boundary; it does not ask the agent to stop itself.

The local record store, memory store, trace sink, and audit store are teaching implementations. Production deployments should connect the same interfaces to the organization’s identity platform, FHIR server, policy gateway, residency-approved telemetry store, and retention-locked audit storage.
