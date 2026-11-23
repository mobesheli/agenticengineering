# Chapter 7: Does It Actually Work?

Companion code for Chapter 7 of *Agentic AI Engineering*, *Does It Actually Work? Evaluating and Testing Agent Systems*.

The chapter builds an evaluation harness for an agent, and this folder is that harness. It contains a small agent under test (a journal entry reviewer), a golden suite of 24 tasks and an abuse suite of 8, a runner that executes repeated trials through the real OpenAI Agents SDK, trajectory graders written in code, a model judge with a calibration report, a paired regression gate, and an evidence pack.

The tests, the walkthrough notebook, and the `--scripted` mode of the examples need no API key. The SDK runner, the reviewer's tools, the graders, and the gate are all real. Only the model's replies are scripted, which also makes the output the same on every run. Without the flag, the examples call a real model and need `OPENAI_API_KEY`.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`openai-agents` is pinned to 0.24.0. The harness stores nothing outside this folder and needs no database.

## Run and verify

Run every command from this folder.

| Command | What it exercises | What you should see |
| --- | --- | --- |
| `python -m pytest -q` | The test suite | 17 tests passing |
| `python -m examples.reliability` | The pass@k, pass^k, and chained-steps arithmetic | The two tables printed in the chapter |
| `python -m examples.show_task` | One golden task and its abuse twin | Two tasks with the same expected outcome |
| `python -m examples.one_task --scripted` | One task run four times through the SDK runner | Three passes, one wrong verdict, pass@4 yes, pass^4 no |
| `python -m examples.suite_run --scripted` | Both suites at four trials each, graded in code | 22 of 24 golden tasks at pass^4, 8 of 8 abuse cases held |
| `python -m examples.judge_calibration` | The judge's agreement with reference labels, from recorded verdicts | Agreement 90%, precision 89%, recall 80%, kappa 0.77 |
| `python -m examples.gate_demo` | The gate applied to three candidate versions | Two blocked, one warned, and one drop judged two ways |
| `python -m examples.evidence_pack` | The evidence pack for the baseline run | Four files and an index |
| `python -m examples.one_task` | One task, four trials, with a real model. Needs `OPENAI_API_KEY` | Four graded trials |
| `python -m examples.suite_run` | The full suite with a real model. Needs `OPENAI_API_KEY` | Your model's own scores, cost, and latency |
| `python -m examples.suite_run --judge` | The same, with the groundedness judge grading every rationale. Needs `OPENAI_API_KEY` | The same report, with judge failures listed |
| `python -m examples.judge_calibration --live` | The real judge on the calibration set. Needs `OPENAI_API_KEY` | A calibration report with your judge's own figures |

A full live run is 128 reviews, and 128 judge calls on top with `--judge`. The suite example prints what the run cost at the prices in `chapter7/models.py`.

The `outputs/` folder holds what every command printed when the chapter was written, including one live run of each live command (the files ending in `_live`). A live model words its rationales differently on every run and can reach different verdicts, so expect your figures to differ from both.

`Chapter_7_Learning_Walkthrough.ipynb` runs the chapter's ideas in order. `python scripts/build_notebook.py` rebuilds and executes it. `python scripts/build_tasks.py` regenerates the three data files.

## Where things are

| Path | What it holds | Chapter section |
| --- | --- | --- |
| `chapter7/models.py` | The model registry and the price table. The only place model names appear | Calibrating the judge against human labels |
| `chapter7/tasks.py`, `data/tasks.json` | The task schema and both suites | Connecting the suite to the Agents SDK |
| `chapter7/environment.py`, `data/policy/approvals_v7.md` | The policy, and a fresh environment for every trial | Connecting the suite to the Agents SDK |
| `chapter7/reviewer.py` | The agent under test and its tools, including two write tools a review must never use | Connecting the suite to the Agents SDK |
| `chapter7/runner.py` | `run_trial` and `run_suite`: repeated trials, a transcript, and a snapshot of the final state | Connecting the suite to the Agents SDK |
| `chapter7/graders.py` | The outcome and trajectory checks, including the loop check that spares retries | Grading and gating the reviewer |
| `chapter7/judge.py`, `data/calibration.json` | The groundedness judge, its typed verdict, and the calibration arithmetic | Calibrating the judge against human labels |
| `chapter7/metrics.py` | `pass_to_k`, `suite_score`, and `paired_drop` | Separating real regressions from noise |
| `chapter7/gates.py` | The regression gate | Writing the gate |
| `chapter7/evidence.py` | The evidence pack | Producing the evidence pack |
| `examples/scripted.py` | The scripted model replies used by the tests, the notebook, and `--scripted`, in four profiles | |

## What is simplified

Every journal entry, vendor, document, and policy clause is invented. The reviewer's tools read the task's fixtures. In production they would be connections to the ledger and the document store.

All the numbers are illustrative. The scripted baseline fails two tasks on purpose, one by recording a verdict before reading the policy and one by missing a split payment in one trial of four, so that the report, the gate, and the evidence pack have something to show. The three candidate profiles in `examples/scripted.py` are written to trigger each branch of the gate.

The calibration set has 30 rationales. The labels are synthetic stand-ins for the ones domain experts would assign, and the judge verdicts in `data/calibration.json` are written to show what a judge's errors look like. The live judge agrees with every label in this set, which says the set is too easy, not that the judge is perfect. A real calibration needs experts, borderline cases, and enough examples of each verdict.

The suites are small enough to read every transcript. With 24 golden tasks, the standard error is about 6 points, and the normal approximation behind it is rough. For a decision that matters, use more tasks and an exact test for paired outcomes.

The gate's thresholds are one conservative policy. Set your own before you look at a candidate's score.

The evidence pack contributes test evidence to a governance review. It does not complete one, and it is not tied to any single regulation. The online sample in `examples/evidence_pack.py` is a placeholder for grades on production traces.

The reviewer and the judge use models from one provider. Where a gate depends on the judge, a second model family is a useful check.

The prices in `chapter7/models.py` are one provider's published standard rates on the date in the file. The model names are the ones the provider published when the chapter was finalized. Change them there, and nowhere else, when the lineup moves.
