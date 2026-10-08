# Chapter 10 Companion Repo

This folder contains the runnable companion for Chapter 10, *Shipping the Thing: Deployment Patterns and Infrastructure*.

Start with `Chapter_10_Shipping_the_Thing_Learning_Walkthrough.ipynb`. It follows the draft section by section: choosing a runtime home, parking approval waits safely, separating the image from runtime state, enforcing tool contracts, naming a release in one bundle, introducing an evaluation gate through monitor, comment, and block modes, rolling back honestly, drilling six kill switches, refusing an incomplete register listing, routing intake to reuse, buy, or build, and putting all four routes on one board.

The default path is deterministic and offline. It makes no model calls, needs no API key, sends no telemetry, and writes all generated evidence beneath the output directory you choose.

## Start Here

Use this order on a first pass:

1. Inspect `template-repository/bundle.yaml` and compute its canonical release digest.
2. Park a synthetic approval and prove that it cannot resume after the release moves.
3. Call one allowed tool operation and refuse an undeclared write before it runs.
4. Run the local pipeline and inspect its deterministic floor, gate, and provenance result.
5. Compare monitor, comment, and block behavior without changing the gate script.
6. Move and roll back a release pointer, then name the state rollback cannot undo.
7. Drill the gateway, identity, contract, runtime, register, and data switches.
8. Watch the fake register refuse an entry with missing evidence, then accept it.
9. Route sample ideas through reuse, buy, and governed-build intake decisions.
10. Generate the four-agent board and hashed deployment evidence pack.

## One-Time Setup

Python 3.11 or later is required. Python 3.12 is recommended.

```bash
cd "chapter 10"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the walkthrough:

```bash
jupyter notebook Chapter_10_Shipping_the_Thing_Learning_Walkthrough.ipynb
```

## Run the Offline Release Review

Run the checked-in release through the local gate, listing exercise, kill-switch drill, and operational board:

```bash
python -m chapter10 --output-dir evidence/latest
```

The command emits:

- `pipeline-report.json`: deterministic-floor, contract, evaluation-gate, and provenance decisions
- `bundle.yaml`: the exact release configuration reviewed
- `listing-demo/`: the refused attempt, created evidence, and accepted register entry
- `agent-board.json`: one row for each build, join, assemble, and buy route
- `kill-switch-drill.json`: a timed staging activation of all six switches
- `manifest.json`: SHA-256 hashes for every artifact in the evidence pack

Verify the manifest from Python:

```bash
python -c 'from pathlib import Path; from chapter10.evidence import verify_manifest; print(verify_manifest(Path("evidence/latest")))'
```

## Run the Pipeline Locally

The same command used by the template workflow runs without a git host:

```bash
python -m chapter10 \
  --pipeline-only \
  --gate-mode block \
  --output-dir artifacts/local
```

`template-repository/pipeline.yaml` shows the generic stage, while `template-repository/.github/workflows/release.yml` shows how a git host makes the named check required. The code deliberately keeps enforcement mode outside the gate algorithm, so an organization can move from `monitor` to `comment` to `block` by changing one value.

The checked-in candidate clears its quality floor, passes every required trial, uses no cached answers, and sits above the baseline interval. Change `template-repository/evals/candidate.json` to explore a held release.

## Watch a Listing Get Refused and Earned

Run only the fake-register exercise:

```bash
python -m chapter10 --listing-demo --output-dir evidence/listing-practice
```

The first check refuses the high-tier maintenance planner because none of its five declared evidence files exists in the practice repository. The exercise then creates the tier record, uncached evaluation report, security review, oversight note, and bundle reference. The same entry passes on the second attempt. The refusal names the missing work instead of returning a generic governance error.

## Try the Intake Funnel

The included intake already describes the maintenance-planning idea:

```bash
python -m chapter10 --intake template-repository/intake.yaml
```

It recommends reusing the listed maintenance planner. Edit a copy to describe a commodity workflow with no internal-inspection requirement and the route becomes `buy`. Describe a company-specific workflow with no marketplace match and the response includes a governed scaffold: identity, budget, monitor-mode gate, and empty golden-set path.

## Project Map

- `Chapter_10_Shipping_the_Thing_Learning_Walkthrough.ipynb`: guided reader experience
- `chapter10/models.py`: typed release, evaluation, register, intake, parked-run, and switch contracts
- `chapter10/release.py`: bundle digest, server-owned approval parking, release pointer, and rollback limits
- `chapter10/contracts.py`: file-backed tool contract and SDK-shaped pre-tool hook
- `chapter10/gate.py`: deterministic secret floor, Wilson-interval comparison, pass-to-the-k check, and local pipeline
- `chapter10/register.py`: file repository, tier requirements, listing check, and refusal-to-acceptance exercise
- `chapter10/adapter.py`: legacy evaluation-suite translation for the join route
- `chapter10/intake.py`: reuse, buy, or build decision and scaffold
- `chapter10/switches.py`: six owned, backed-up, independently drillable kill switches
- `chapter10/board.py`: shared operational board for all four routes
- `chapter10/evidence.py`: release-review artifacts and hashed manifest
- `template-repository/`: image boundary, immutable bundle, contracts, policy, eval reports, provenance, pipeline, and workflow
- `data/register/`: evidence requirements, deliberately incomplete candidate, and four operational entries
- `data/catalog/marketplace.yaml`: small internal marketplace searched by intake
- `assets/`: the nine figures from the Chapter 10 draft
- `tests/`: offline unit, integration, CLI, pipeline, listing, and evidence tests

## Verify Everything

Run the complete offline suite:

```bash
pytest -q
```

Check formatting and imports:

```bash
ruff check .
ruff format --check .
```

Rebuild and execute the checked-in notebook:

```bash
python scripts/build_notebook.py
jupyter nbconvert --to notebook --execute \
  Chapter_10_Shipping_the_Thing_Learning_Walkthrough.ipynb \
  --output /tmp/chapter10-executed.ipynb \
  --ExecutePreprocessor.timeout=180
```

Run the CLI smoke test directly:

```bash
python -m chapter10 --output-dir /tmp/chapter10-evidence
```

## Deployment and Trust Boundaries

- Every model, prompt, tool catalog, policy pack, sandbox, image, memory schema, and evaluation suite is named by an immutable release bundle.
- The image and sandbox use digests. The example package lock uses exact versions; production builds should add hashes from the approved package mirror.
- No secret belongs in the image, prompt, context file, register, or generated evidence. Workload identity is the only credential mode accepted by the checked-in tool contract.
- Parked run state is server-owned. A client cannot submit approvals by sending serialized state, and a run parked under an old bundle restarts instead of resuming.
- A model change, fallback change, quantization change, or serving-stack change is a release and must earn a fresh evaluation report.
- Release certification refuses cached answers and required cases that do not pass every trial.
- A rollback moves a pointer. It cannot erase newer memory, reverse completed effects, or safely resume an approval parked under another release.
- Every kill switch has an owner and a different backup. Tenant targeting lets Plant D stop without taking Plants A, B, and C down with it.
- The register and gate are files and code the organization owns. Bought agents appear on the same board, with allocated cost and unobservable drift fields kept explicit.

The local store, pipeline, signature record, register, and board are teaching implementations. Production deployments should connect the same contracts to the organization’s durable workflow engine, identity directory, model gateway, artifact registry, git-host rulesets, telemetry plane, data certification service, and incident system.
