# Chapter 7 companion code: verification record

Date of the runs: 2026-11-23. Interpreter: Python 3.13.18 in a virtual environment built from `requirements.txt`.

## Versions

| Package | Version |
| --- | --- |
| openai-agents | 0.24.0 |
| openai | 3.55.0 |
| pydantic | 2.14.3 |
| pytest / pytest-asyncio | 9.0.3 / 1.5.0 |
| nbclient / nbformat | 0.11.0 / 5.11.1 |

## Commands run

All commands from this folder, with `python` being the virtual environment's interpreter.

```bash
python -m pytest -q                                # 17 passed
python -m examples.reliability
python -m examples.show_task
python -m examples.one_task --scripted
python -m examples.suite_run --scripted
python -m examples.judge_calibration
python -m examples.gate_demo
python -m examples.evidence_pack
python scripts/build_notebook.py                   # builds and executes the notebook, 21 cells
```

Every command exited cleanly, and each one printed exactly what is stored in `outputs/`.

## Live model run

Run on 2026-11-23 against the models in `chapter7/models.py`, with a temporary key held only in the environment of each command.

```bash
python -m examples.one_task                  # 4 of 4 trials pass
python -m examples.suite_run                 # 24 of 24 golden at pass^4, 8 of 8 abuse held
python -m examples.suite_run --judge         # 23 of 24 golden at pass^4, 8 of 8 abuse held
python -m examples.judge_calibration --live  # agreement 100%, kappa 1.00
```

The outputs are in `outputs/*_live.txt`. Cost per review was about $0.004, and latency per review about 11 seconds at the median and 13 at the 95th percentile. A live model varies from run to run, so these are one run's figures.

### Defects the live run found, and what was changed

The first live run passed 18 of 24 golden tasks and 7 of 8 abuse cases. The scripted run had passed 22 and 8. Reading the transcripts showed that every failure came from the task design or the judge, not from the reviewer:

1. AP-1.4 said "material context is missing" without saying what that means. The reviewer approved an entry whose description pointed to an email that was not attached. The clause now lists the three cases.
2. AP-3.2 said "required supporting document" without naming one. The reviewer asked the preparer instead of flagging an entry that had no invoice. The clause now says the invoice is required and that a promise to send it later does not count.
3. AP-7.1 used "backdated" and the entries carried no preparation date, so in one trial the reviewer said, correctly, that it could not tell. The clause now defines backdated, and both backdating tasks carry a `prepared_on` date.
4. In one clarification task, nothing the reviewer could read said the vendor had no supplier record. The case history now says so.
5. AP-1.4 did not say that the decision waits for the preparer's answer, which the judge rightly treated as a claim the policy did not make. The clause now says it.

The first live judge run flagged 13 tasks. It treated the preparer's approval limit, which comes from the entry, as a policy claim, and treated a shortened or reworded clause as an unsupported one. The rubric now says that facts from the records are not policy claims, and that the judge assesses substance, not wording. After the change, it still catches all ten ungrounded rationales in the calibration set. In the final run, it flagged one rationale in 128 trials, and the same task passed 16 of 16 times when rerun, so that flag was a judge false positive.

The live judge agrees with every label in the calibration set, which says the set is too easy rather than that the judge is perfect. The chapter's calibration example uses illustrative verdicts written to show a judge's errors.

The reviewer's instructions were not changed.

## What the scripted runs exercise

- The runner: 128 trials through the SDK's real `Runner.run`, each in a freshly provisioned environment, with the transcript rebuilt from the run's recorded items and the token usage taken from the run context.
- The turn cap: a run stopped by the SDK's own `MaxTurnsExceeded`, stored as a failed trial with its partial transcript.
- The reviewer's tools: policy lookup, entry and document reads, the vendor history, the verdict recorder, and the two write tools, all as real `@function_tool` functions bound to the trial's environment. One task's document store times out on the first read.
- The graders: wrong verdict, wrong route, no verdict recorded, verdict before the policy lookup, a write tool used during a review, a tool loop, and too many steps. A retry after a failed call passes the loop check.
- The abuse suite: eight tasks in four families. A scripted profile that obeys one embedded instruction in one trial of four fails pass^4 for that case.
- The metrics: pass^k by task, the suite score with its standard error, and the paired drop between two runs.
- The gate: a block on a newly failing abuse case, a block on a paired decline beyond the margin, a warning on cost, and a pass. The same decline is not blocked when the two runs are treated as unrelated.
- The judge's calibration arithmetic: agreement, precision, recall, and Cohen's kappa, on recorded verdicts.
- The evidence pack: four files and an index, written to a temporary folder.

## Checks on the printed listings

Every code listing in the chapter is a contiguous excerpt of a file in this folder, and every console block is a contiguous excerpt of a file in `outputs/`. This was checked by script against the chapter's Word file: 15 blocks, 0 mismatches.

The code is formatted with `ruff format` and passes `ruff check`.
