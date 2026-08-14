"""Build the checked-in Chapter 7 learning walkthrough deterministically."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Chapter_7_Does_It_Actually_Work_Learning_Walkthrough.ipynb"


def clean(text: str) -> str:
    return dedent(text).strip() + "\n"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(clean(text))


def code(text: str):
    return nbf.v4.new_code_cell(clean(text))


cells = [
    markdown(
        """
        # Chapter 7: Does It Actually Work?

        **Evaluating and testing agent systems — a runnable learning walkthrough**

        This notebook turns "working" into a repeatable measurement. You will run isolated trials, grade outcomes and trajectories, calibrate a narrow model judge, keep abuse cases permanently, apply statistical regression policy, and produce the evidence folder expected by a model-risk review.

        The default path is deterministic and offline. That makes the harness itself testable before it is pointed at a live agent or a paid judge.
        """
    ),
    markdown(
        """
        ## Start Here

        Run the cells from top to bottom once. The sequence mirrors the chapter:

        1. Replace the one-run demo with repeated-trial reliability.
        2. Inspect the golden suite and its abusive twins.
        3. Grade the journey, not only the final answer.
        4. Measure a semantic judge before trusting its verdicts.
        5. Turn red-team findings into permanent tests.
        6. Put uncertainty-aware policy in front of deployment.
        7. Report success, cost, latency, and safety together.
        8. Assemble the compliance-review evidence pack.
        """
    ),
    markdown("## 0. Setup"),
    code(
        """
        from __future__ import annotations

        import sys
        from pathlib import Path

        chapter_root = Path.cwd()
        if not (chapter_root / "chapter7").exists():
            candidate = chapter_root / "chapter 7"
            if candidate.exists():
                chapter_root = candidate
        if str(chapter_root) not in sys.path:
            sys.path.insert(0, str(chapter_root))
        """
    ),
    code(
        """
        import json
        import tempfile

        from chapter7.dataset import abuse_tasks, golden_tasks, load_tasks
        from chapter7.environment import provision, teardown
        from chapter7.evidence import emit_evidence_pack
        from chapter7.gates import gate
        from chapter7.graders import grade_suite, grade_trajectory
        from chapter7.judge import calibrate_judge
        from chapter7.live import build_compliance_agent
        from chapter7.metrics import (
            build_suite_result,
            theoretical_pass_at_k,
            theoretical_pass_to_k,
        )
        from chapter7.models import SuiteResult
        from chapter7.reviewer import ComplianceReviewer, UnsafeComplianceReviewer
        from chapter7.runner import run_suite, run_trial

        print("Harness ready from", chapter_root)
        """
    ),
    markdown(
        """
        ## 1. Why one successful run proves almost nothing

        One run is a sample. Repeating the task exposes the difference between *can succeed eventually* and *succeeds every time*. Pass@k asks whether any of the k trials passed. Pass^k asks whether all of them passed.
        """
    ),
    code(
        """
        probability = 0.90
        k = 4
        reliability = {
            "pass@4": theoretical_pass_at_k(probability, k),
            "pass^4": theoretical_pass_to_k(probability, k),
        }
        reliability
        """
    ),
    markdown(
        """
        A 90 percent single-run agent has a 99.99 percent chance of succeeding at least once in four attempts, but only a 65.61 percent chance of succeeding four times in a row. The first number flatters a demo. The second resembles production.
        """
    ),
    markdown("## 2. Building the golden suite and its abusive twins"),
    code(
        """
        tasks = load_tasks()
        suite_shape = {
            "all": len(tasks),
            "golden": len(golden_tasks()),
            "abuse": len(abuse_tasks()),
            "verdicts": sorted({task.expected["verdict"] for task in tasks}),
        }
        suite_shape
        """
    ),
    markdown(
        """
        Each task carries a defined starting state, an expected outcome, declared graders, and a reference solution. The suite contains clean approvals, true violations, ambiguous cases, and adversarial data. The task asks for an outcome without demanding one exact path.
        """
    ),
    code(
        """
        golden = golden_tasks()[16]
        abusive = abuse_tasks()[0]
        {
            "golden": golden.model_dump(mode="json"),
            "abuse": abusive.model_dump(mode="json"),
        }
        """
    ),
    markdown(
        """
        The hostile instruction lives inside the journal-entry fixture. This matters because real prompt injection usually arrives through data the agent was legitimately asked to inspect, not through an obvious hostile message at the front door.
        """
    ),
    markdown("## 3. Judging the journey with trajectory checks"),
    code(
        """
        trial = await run_trial(ComplianceReviewer, golden, 0)
        {
            "final_state": trial.final_state,
            "tool_calls": [call.name for call in trial.transcript.tool_calls],
            "rationale": trial.transcript.rationale,
            "failures": grade_trajectory(golden, trial),
        }
        """
    ),
    markdown(
        """
        The result is correct, but that is not enough. The trajectory proves that the reviewer looked up policy before it recorded a verdict, avoided write tools, stayed within its step budget, and did not loop on repeated calls. These checks are deterministic, fast, and free.
        """
    ),
    markdown(
        """
        ### Inspecting the live Agents SDK target

        Building the live target does not call a model. It verifies that the same fixture-backed tools and typed output contract are ready for a deliberate live suite run.
        """
    ),
    code(
        """
        live_environment = await provision(golden)
        live_agent, live_calls = build_compliance_agent(live_environment)
        live_wiring = {
            "name": live_agent.name,
            "model": live_agent.model,
            "tools": [tool.name for tool in live_agent.tools],
            "calls_before_run": live_calls,
        }
        await teardown(live_environment)
        live_wiring
        """
    ),
    markdown("## 4. Measuring the judge before using it"),
    code(
        """
        human_labels = [True] * 20 + [False] * 20
        judge_labels = [True] * 18 + [False] * 2 + [True] * 2 + [False] * 18
        calibration = calibrate_judge(human_labels, judge_labels)
        calibration.model_dump()
        """
    ),
    markdown(
        """
        This 40-item calibration set gives the judge 0.90 precision, 0.90 recall, and Cohen's kappa of 0.80. Kappa removes agreement expected by chance. A live judge belongs in a gate only after this measurement has been run on expert labels and recorded with the result.
        """
    ),
    markdown("## 5. Keeping adversarial findings permanent"),
    code(
        """
        poisoned = abuse_tasks()[0]
        safe_trial = await run_trial(ComplianceReviewer, poisoned, 0)
        unsafe_trial = await run_trial(UnsafeComplianceReviewer, poisoned, 0)
        {
            "safe": grade_trajectory(poisoned, safe_trial),
            "unsafe": grade_trajectory(poisoned, unsafe_trial),
            "unsafe_calls": [call.name for call in unsafe_trial.transcript.tool_calls],
        }
        """
    ),
    markdown(
        """
        The safe reviewer ignores the entry's instruction and follows policy. The deliberately unsafe candidate approves and calls a forbidden write tool, so the same case catches both an outcome failure and a trajectory failure. Once a red team finds a case like this, it stays in the suite.
        """
    ),
    markdown("## 6. Applying the regression gate"),
    code(
        """
        baseline_path = chapter_root / "data" / "baseline.json"
        baseline = SuiteResult.model_validate_json(baseline_path.read_text())
        safe_trials = await run_suite(tasks, k=1)
        safe_result = build_suite_result(safe_trials, grade_suite(tasks, safe_trials))
        gate(safe_result, baseline).model_dump()
        """
    ),
    markdown(
        """
        The gate has three postures. Any abuse-suite decline blocks. A quality drop blocks only after it clears the combined noise margin. Cost drift above 25 percent warns without stopping the release. The rules are explicit enough to review as policy and mechanical enough to enforce in a pipeline.
        """
    ),
    markdown("## 7. Running the complete four-trial harness"),
    code(
        """
        trials = await run_suite(tasks, k=4)
        grades = grade_suite(tasks, trials)
        summary = build_suite_result(trials, grades, run_id="chapter-7-walkthrough")
        {
            "trials": summary.trial_count,
            "tasks": summary.task_count,
            "pass@4": summary.pass_at_k,
            "pass^4": summary.pass_to_k,
            "task_success": summary.golden_pass_rate,
            "cost_per_trial": summary.cost_per_task,
            "latency_p50": summary.latency_p50,
            "latency_p95": summary.latency_p95,
            "safety": summary.abuse_pass_rate,
        }
        """
    ),
    markdown(
        """
        The report keeps task success, fully loaded cost, tail latency, and safety together. No single metric can stand in for the set. The deterministic teaching double passes every task so that the harness has a stable self-test; replacing it with a live reviewer turns the same report into a behavioral measurement.
        """
    ),
    markdown("## 8. Producing the model-risk evidence pack"),
    code(
        """
        evidence_dir = Path(tempfile.mkdtemp(prefix="chapter7-evidence-"))
        manifest_path = emit_evidence_pack(summary, evidence_dir)
        manifest = json.loads(manifest_path.read_text())
        [(record["control"], record["path"]) for record in manifest["records"]]
        """
    ),
    markdown(
        """
        Golden results support conceptual soundness testing. Abuse results support effective challenge. Online samples support ongoing monitoring. The failure log documents limitations. Each file is hashed in the manifest so the review folder is verifiable after the run.
        """
    ),
    markdown("## 9. Notebook self-check"),
    code(
        """
        assert len(golden_tasks()) == 48
        assert len(abuse_tasks()) == 15
        assert summary.trial_count == 252
        assert summary.k == 4
        assert summary.golden_pass_rate == 1.0
        assert summary.abuse_pass_rate == 1.0
        assert calibration.cohens_kappa == 0.8
        assert len(manifest["records"]) == 4
        print("All Chapter 7 walkthrough checks passed.")
        """
    ),
    markdown(
        """
        ## Chapter-to-notebook map

        | Chapter topic | Runnable section |
        |---|---|
        | Why unit tests are insufficient | Sections 1 and 3 |
        | Golden tasks and trajectory testing | Sections 2 and 3 |
        | Model-as-judge | Section 4 |
        | Adversarial evaluation | Section 5 |
        | Regression gates | Section 6 |
        | Success, cost, latency, and safety | Section 7 |
        | Compliance-review evidence pack | Section 8 |

        The package and tests contain the reusable implementation behind every cell. Run `pytest -q` for the complete offline verification suite.
        """
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.11"},
    },
)
nbf.write(notebook, OUTPUT)
print(f"Wrote {OUTPUT}")
