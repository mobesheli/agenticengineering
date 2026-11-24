# Chapter 8: Securing Agents With Guardrails and Governance

Companion code for Chapter 8 of *Agentic AI Engineering*, *Securing Agents With Guardrails and Governance*.

The chapter takes the medication reconciliation agent from Chapter 4 and gives it controls that a hospital security review can assess. This folder holds each control as code: a tool catalog enforced by a guardrail on every call, a split session with a read phase and a write phase, an approval bound to one exact action, a write policy with a budget and a clock, a redacting trace exporter with a canary test, a linter for the agent's own approval requests, a decision log checked against a signed checkpoint, and an emergency stop with a drill.

The tests, the walkthrough notebook, and the examples need no API key. The SDK runner, the tools, the guardrail, the approval pause, the policy, and the record store are all real. Only the model's replies are scripted, which makes the output the same on every run and lets the examples script a model that does what an attacker wants. Three examples can also call real models and need `OPENAI_API_KEY` for that.

Every patient record in `data/fixtures/` is synthetic.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Every package the chapter's code imports is pinned in `requirements.txt`, including `openai-agents` at 0.24.0. The guardrail and approval interfaces in the SDK still change between releases, so run the tests after any upgrade.

## Run and verify

Run every command from this folder.

| Command | What it exercises | What you should see |
| --- | --- | --- |
| `python -m pytest -q` | The test suite | 36 tests passing |
| `python -m examples.rule_of_two` | The Rule of Two applied to three session designs | One design with all three properties, two with two |
| `python -m examples.guardrail_demo` | The catalog guardrail on six tool calls | One call allowed, four that end the run, one refused while the run continues |
| `python -m examples.attack` | Scripted readers that obey a hostile clinical note, and a writer that adds a change | Every attempt stopped, and no write in any run |
| `python -m examples.policy_demo` | The write policy on nine attempts | One allowed, eight denied, each with the rule that decided |
| `python -m examples.reconcile --scripted` | The whole split session: read, review, sign, write | Four changes proposed, one signature, two linked decision records |
| `python -m examples.linter_demo` | The approval linter on three requests | One clean, two flagged |
| `python -m examples.redaction_demo` | The canary test on a trace exported with and without redaction | Four canaries in the raw export and none anywhere else |
| `python -m examples.audit_demo` | The decision log checked against its signed checkpoint after four kinds of tampering | "intact", then four different failures |
| `python -m examples.stop_drill` | The emergency stop pressed with one write committed and one waiting | Every later path refused, and the earlier write reported |
| `python -m examples.evidence_pack` | The security evidence pack and its manifest | Eight files and their hashes |
| `python -m examples.reconcile` | The split session with real models. Needs `OPENAI_API_KEY` | The same path, in the models' own words |
| `python -m examples.redaction_demo --live` | The canary test with a real model. Needs `OPENAI_API_KEY` | The same counts |
| `python -m examples.live_check` | Both phases, repeated, on the clean record and the hostile one. Needs `OPENAI_API_KEY` | A tally of what the models did, with the controls checked after every run |

The `outputs/` folder holds what every scripted command printed when the chapter was written, and `outputs/live/` holds one run of each live command. `tests/test_outputs.py` checks that each example still prints exactly what is stored. A live model words its messages differently on every run.

`Chapter_8_Learning_Walkthrough.ipynb` runs the chapter's ideas in order. `python scripts/build_notebook.py` rebuilds and executes it.

## Where things are

| Path | What it holds | Chapter section |
| --- | --- | --- |
| `chapter8/threat.py` | The Rule of Two as a check, and the autonomy a risk tier allows | Applying the Rule of Two |
| `chapter8/proposal.py` | The typed findings and proposal, and the validation that runs before anyone approves | Designing architectures that limit prompt-injection impact |
| `chapter8/catalog.py`, `data/catalog/` | The tool catalog, the guardrail that enforces it, and the check on pinned tool descriptions | Understanding SDK guardrail boundaries |
| `chapter8/gateway.py` | The event log and the two kinds of denial | Understanding SDK guardrail boundaries |
| `chapter8/approvals.py` | The action hash and the approval store | Enforcing controls with lifecycle hooks |
| `chapter8/policy.py`, `data/policies/` | The write policy, its limits, and the atomic authorization | Enforcing policy as code with budgets and time windows |
| `chapter8/session.py` | Scopes for each phase, the session, and a stand-in for the SMART on FHIR launch | Limiting the records and tools it can access |
| `chapter8/records.py` | A stand-in for the record server, which checks every token itself and writes its own audit events | Making the catalog the permission model |
| `chapter8/redaction.py` | The redacting exporter, the keyed fingerprint, and the canary search | Redacting sensitive information before trace export |
| `chapter8/reader.py`, `chapter8/writer.py` | The two agents of the split session | Real-world pattern |
| `chapter8/phases.py` | The read phase, the parked write, and the resume on a fresh session | Requiring approvals based on consequences |
| `chapter8/review.py`, `chapter8/linter.py` | The reviewer's packet, evidence first, and the linter for the agent's own words | Treating approval fatigue as an attack surface |
| `chapter8/registry.py`, `chapter8/stop.py`, `data/registry.yaml` | The agent registry and the emergency stop | Implementing emergency stop controls |
| `chapter8/commit.py` | The one path a write can take, and the decision records it leaves | Designing the decision record |
| `chapter8/audit.py` | The decision record, the chain, the notary, and the FHIR audit event | Recording agent decisions for audit and compliance |
| `chapter8/evidence.py` | The evidence pack and its manifest | Assembling the evidence pack |
| `chapter8/responsible.py` | An outcome-rate screen and a disclosure wrapper | Governing fairness, transparency, and accountability in agent actions |
| `chapter8/harness.py` | Everything above wired together | Real-world pattern |
| `chapter8/settings.py` | Model names and run limits | Technical requirements |
| `examples/scripted.py` | The scripted model replies, including the ones that obey the attacker | Technical requirements |

## What is a stand-in

Three classes stand in for systems a hospital already runs, so that the examples work on a laptop: `Tokens` for the authorization server and the SMART on FHIR launch, `RecordStore` for the FHIR server, and `Notary` for a signing service with its own key. The decision log and the event log are held in memory. In production they are an append-only store with a retention lock that the agent's identity cannot reach.
