# Chapter 2 Companion Repo

This folder contains a small training project for Chapter 2, *From Zero to Agent: Building with the OpenAI Agents SDK*.

The goal is clarity, not cleverness. The project uses a simple insurance claims workflow so readers can see the five subsystem ideas in code:

- reasoning core: `claims_pipeline/agents.py`
- tool registry: `claims_pipeline/tools.py`
- constraints: `claims_pipeline/guardrails.py`
- orchestration: `claims_pipeline/pipeline.py`
- structured memory for the sample data: `claims_pipeline/data.py`

## Folder Layout

- `claims_pipeline/`: shared code for the sample workflow
- `main.py`: small command-line entry point
- `tests/`: unit tests for the offline flow and SDK wiring
- `requirements.txt`: pinned packages used for this chapter

## Quick Start

```bash
cd "chapter 2"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py list-claims
python main.py offline --claim CLM-1001
pytest
```

## Live SDK Run

The live OpenAI Agents SDK path needs an API key:

```bash
export OPENAI_API_KEY="your-api-key"
python main.py live --claim CLM-1001
```

If the key is valid but the account has no remaining quota, the script exits with a clear quota message instead of a long stack trace.

## What Was Verified

I verified the offline pipeline and the local SDK wiring with tests. On March 30, 2026, this machine did not have `OPENAI_API_KEY` configured, so real model calls were not executed here.

I also had to create a Python 3.11 virtual environment because the machine defaulted to Python 3.9, while this chapter requires Python 3.10 or later.
