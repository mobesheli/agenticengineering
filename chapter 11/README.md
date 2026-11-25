# Chapter 11: Operating, Evolving, and Retiring Agents

Companion code for Chapter 11 of *Agentic AI Engineering*. It follows the
maintenance planning agent through its first year on the platform: a model that
changed without a release, a promotion case that failed on the reviewers, a
memory store that had gone stale, a fleet nobody had counted, a fix the agent
proposed for itself, and a retirement.

Nothing here needs an API key except `examples/live_check.py`. The policy code is
plain Python over the files in `data/`. The memory consolidator is a real SDK
agent with a structured output. In the examples, its replies are scripted, so the
printed results are the same on every run. All plant and fleet data is synthetic.
The settings under `observed_at_approval` in `data/bundle.yaml` are what the
provider reported for that model on the date in `VERIFICATION.md`.

## Set up

```console
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Python 3.11 or later. The package versions are pinned in `requirements.txt`
(`openai-agents==0.24.0`).

## What is in the folder

| Path | What it is |
| --- | --- |
| `chapter11/effective.py` | Reads what the provider actually ran from its response, and compares it with the approved bundle |
| `chapter11/drift.py` | The drift check: five signals in, one decision out |
| `chapter11/autonomy.py` | The ladder: the ceiling, the promotion rule, the rule that drops |
| `chapter11/mandate.py` | A spending mandate: scoped, capped, expiring, revocable |
| `chapter11/memory.py` | A memory store, the consolidator agent, the checks on a merge, and the hygiene pass |
| `chapter11/lineage.py` | From one source to every copy: quarantine, erasure, and a safe restore |
| `chapter11/fleet.py` | Listing gaps, reconciliation with vendor registries, contract breaks |
| `chapter11/improve.py` | The gate for a fix the agent proposed, and the 30-minute pause rule |
| `chapter11/retire.py`, `systems.py` | The retirement script and stand-ins for the systems it touches |
| `data/` | The approved bundle, the bands, the ladder, the evidence, the memories, the fleet, and the year |
| `examples/` | One runnable script for each result printed in the chapter |
| `outputs/` | What each example printed when the chapter was written |
| `tests/` | 51 tests, including one that reruns every example against `outputs/` |
| `Chapter_11_Learning_Walkthrough.ipynb` | The chapter as a notebook, with no key needed |

## Run the examples

```console
python -m examples.drift_view
python -m examples.promotion
python -m examples.mandate_demo
python -m examples.hygiene
python -m examples.lineage_demo
python -m examples.fleet_demo
python -m examples.improvement
python -m examples.retirement
python -m examples.year_board
```

With a key in `OPENAI_API_KEY`, `python -m examples.live_check` runs the
consolidator against a live model, prints the effective configuration the
provider reports, compares it with the bundle, and checks that a setting changed
on purpose is caught.

## Using it on your own agent

Start with three files. Put what your provider reports on the day your gate
passes into the bundle, as `observed_at_approval`. Write your bands into
`data/readings.yaml` in the unit of each signal. Write the evidence each step up
the ladder needs into `data/ladder.yaml`, and keep the ceiling out of that file,
in the register entry, where the people who own the risk can set it.
