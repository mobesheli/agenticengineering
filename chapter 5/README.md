# Chapter 5 Companion Repo

This folder contains the companion learning material for Chapter 5, *Who Runs the Show: Orchestration Patterns and Model Routing*.

Start with `Chapter_5_Who_Runs_the_Show_Learning_Walkthrough.ipynb`. It follows the chapter section by section and turns the orchestration ideas into small runnable examples: code-led versus model-led control, loop budgets, checkpointing, request routers, model routers, plan validation, fan-out, human approval routes, and the financial crime alert triage pyramid.

## Start Here

Use this order the first time you open the project:

1. Read the notebook section map.
2. Run the setup cell.
3. Work through the orchestration dial and loop-control examples.
4. Run the checkpointing and router examples.
5. Tune the router threshold and inspect the confusion matrix.
6. Read the model registry and canary cells carefully.
7. Run the plan, fan-out, and human approval examples.
8. Finish with the alert triage pyramid and notebook self-check.

## One-Time Setup

Python 3.10 or later is required. Python 3.11 is recommended.

```bash
cd "chapter 5"
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

- `Chapter_5_Who_Runs_the_Show_Learning_Walkthrough.ipynb`: guided notebook for readers
- `chapter5/models.py`: one-place model registry used by the notebook examples
- `requirements.txt`: notebook dependencies

## What Readers Build

The notebook builds the conceptual and code surface of Chapter 5 in this order:

1. A code-led invoice pipeline where Python owns the consequence of a model extraction.
2. A loop controller with explicit final-output, handoff, exception, and max-turn endings.
3. A compound-reliability table and a checkpointed workflow that resumes after a crash.
4. A request router with an `other` category, confidence threshold, and human fallback.
5. A router evaluation with a confusion matrix, precision, recall, and threshold tuning.
6. A model registry, deterministic canary split, tier routing, and cost arithmetic.
7. A typed plan validator and a safe fan-out pattern for independent specialist work.
8. A human approval route that pauses without holding a worker alive.
9. A financial crime alert triage pyramid where the model recommends, code disposes, and humans remain accountable.

Most cells run offline with deterministic teaching doubles. The examples keep the same control-flow shape as the OpenAI Agents SDK snippets in the chapter, but avoid requiring a live API key so readers can focus on orchestration mechanics first.

## Code Reading Guidance

The notebook code is intentionally more commented than production code. Those comments explain why each boundary, threshold, checkpoint, model choice, plan check, approval package, and disposition branch exists. Readers should run the notebook from top to bottom once before copying any individual snippet into a real project.
