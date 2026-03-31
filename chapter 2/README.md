# Chapter 2 Companion Repo

This folder contains the companion project for Chapter 2, *From Zero to Agent: Building with the OpenAI Agents SDK*.

If you want the easiest learning path, start with `Chapter_2_Learning_Walkthrough.ipynb`. It explains the system visually and walks through the commands in the same order a reader should run them.

## Start Here

Use this order the first time you open the project:

1. Set up the environment.
2. Run `python main.py describe`.
3. Run the offline claims one by one.
4. Run `pytest`.
5. Use the live command only after setting `OPENAI_API_KEY`.

## One-Time Setup

Python 3.10 or later is required. Python 3.11 is recommended.

```bash
cd "chapter 2"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If you want to open the notebook locally:

```bash
python -m pip install notebook
jupyter notebook
```

## Command Guide

| Goal | Command | What it does |
| --- | --- | --- |
| See the sample claim ids | `python main.py list-claims` | Prints the three built-in claims |
| Inspect the app structure | `python main.py describe` | Shows agents, tools, guardrails, and handoffs |
| Run the safest first demo | `python main.py offline --claim CLM-1001` | Runs the local deterministic path without calling the API |
| See the missing-document path | `python main.py offline --claim CLM-1002` | Stops after intake and asks for missing documents |
| See the escalation path | `python main.py offline --claim CLM-1003` | Routes the claim to human review |
| Run the automated checks | `pytest` | Verifies the chapter code still behaves as expected |
| Run the live SDK version | `python main.py live --claim CLM-1001` | Uses the OpenAI Agents SDK with a real API key |

## Recommended First Run

Copy and paste these commands in this order:

```bash
cd "chapter 2"
source .venv/bin/activate
python main.py describe
python main.py offline --claim CLM-1001
python main.py offline --claim CLM-1002
python main.py offline --claim CLM-1003
pytest
```

What you should see:

- `describe` explains the system layout.
- `CLM-1001` ends with `review_complete`.
- `CLM-1002` ends with `request_documents`.
- `CLM-1003` ends with `escalated`.

## Live SDK Run

Only use the live path after the offline path is clear.

```bash
export OPENAI_API_KEY="your-api-key"
python main.py live --claim CLM-1001
```

Start with `CLM-1001` because it is the simplest case. After that, try `CLM-1002` and `CLM-1003` and compare the live output to the offline results.

If the key is valid but the project has no remaining quota, the script exits with a clear quota message instead of a long stack trace.

## Project Map

- `Chapter_2_Learning_Walkthrough.ipynb`: guided notebook for readers
- `main.py`: small command-line entry point
- `claims_pipeline/agents.py`: agent definitions and handoffs
- `claims_pipeline/tools.py`: function tools
- `claims_pipeline/guardrails.py`: input and output checks
- `claims_pipeline/pipeline.py`: workflow orchestration and deterministic rules
- `claims_pipeline/data.py`: sample claims and policies
- `tests/`: verification for the chapter project

## What Was Verified

I verified the offline pipeline, notebook code cells, and local SDK wiring on March 31, 2026.
