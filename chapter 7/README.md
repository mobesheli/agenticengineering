# Chapter 7 Companion Repo

This folder contains the runnable companion for Chapter 7, *Does It Actually Work? Evaluating and Testing Agent Systems*.

Start with `Chapter_7_Does_It_Actually_Work_Learning_Walkthrough.ipynb`. It follows the draft section by section: repeated-trial reliability, the 48-task golden suite, trajectory checks, groundedness judging and calibration, 15 permanent abuse cases, statistical deployment gates, the four operating metrics, and the compliance-review evidence pack.

## Start Here

Use this order on a first pass:

1. Compare pass@k with pass^k for the same single-trial success probability.
2. Inspect the golden and abuse datasets and their fixture-backed task schema.
3. Run four isolated trials for one journal-entry review.
4. Grade the outcome and the policy-before-verdict trajectory.
5. Calibrate the narrow groundedness judge against human labels.
6. Run an unsafe candidate against a poisoned fixture.
7. Compare the candidate with the accepted baseline through the regression gate.
8. Run all 63 tasks at four trials each and emit the SR 11-7 evidence folder.

## One-Time Setup

Python 3.11 or later is required. Python 3.12 is recommended.

```bash
cd "chapter 7"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the walkthrough:

```bash
jupyter notebook Chapter_7_Does_It_Actually_Work_Learning_Walkthrough.ipynb
```

The default route is deterministic and offline. The live reviewer and semantic judge adapters use the configured model registry only when you deliberately select them.

## Project Map

- `Chapter_7_Does_It_Actually_Work_Learning_Walkthrough.ipynb`: guided reader experience
- `chapter7/dataset.py`: 48 golden tasks and 15 abuse cases
- `chapter7/environment.py`: isolated fixture provisioning and teardown
- `chapter7/reviewer.py`: stable compliance-review teaching double and unsafe challenger
- `chapter7/live.py`: optional OpenAI Agents SDK evaluation target
- `chapter7/models_registry.py`: performer and judge model roles
- `chapter7/runner.py`: bounded parallel trial execution
- `chapter7/graders.py`: deterministic outcome and trajectory grading
- `chapter7/judge.py`: strict groundedness judge and calibration statistics
- `chapter7/metrics.py`: pass@k, pass^k, uncertainty, cost, and latency
- `chapter7/gates.py`: hard safety, soft quality, and cost-trend policy
- `chapter7/evidence.py`: SR 11-7 control mapping and hashed evidence manifest
- `data/fixtures/`: realistic journal-entry, abuse, and memory fixtures
- `data/policies/approvals_v7.md`: versioned policy under evaluation
- `data/baseline.json`: accepted comparison point for the offline gate
- `scripts/run_regression_gate.py`: pipeline-friendly gate command
- `tests/`: offline unit, integration, safety, statistics, and evidence tests

## Run the Suite

Run the complete offline harness and print its report:

```bash
python -m chapter7 --trials 4 --evidence-dir evidence/latest
```

To evaluate the live Agents SDK target, export `OPENAI_API_KEY` and select the live route explicitly. Start with one trial while checking cost and behavior:

```bash
python -m chapter7 --live --trials 1 --evidence-dir evidence/live
```

Run the deployment gate. A blocked verdict returns a nonzero exit status:

```bash
python scripts/run_regression_gate.py
```

Run the automated tests:

```bash
pytest -q
```

Rebuild the checked-in notebook after editing its source:

```bash
python scripts/build_notebook.py
```

## Design Boundaries

- Every trial receives a fresh environment, so repeated attempts do not share state.
- The task schema declares fixtures, expected outcomes, graders, and a reference solution.
- Deterministic checks grade mechanical facts before any model judge is considered.
- Abuse cases poison documents, vendor fields, or history rather than relying on obvious hostile user prompts.
- Safety regression blocks immediately. Quality regression must clear the combined noise margin. Cost drift warns.
- The offline reviewer is a testing instrument, not a claim that deterministic rules replace the production agent.

## Evidence Output

`emit_evidence_pack` maps the suite results into four model-risk controls:

- golden-suite results to conceptual soundness testing
- abuse-suite results to effective challenge
- online sample grades to ongoing monitoring
- failure analysis to documented limitations

The manifest records a SHA-256 digest for each artifact so a review team can verify that the evidence folder has not changed after the run.
