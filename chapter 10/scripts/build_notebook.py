"""Build the checked-in Chapter 10 learning walkthrough deterministically."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Chapter_10_Shipping_the_Thing_Learning_Walkthrough.ipynb"


def clean(text: str) -> str:
    return dedent(text).strip()


def markdown(text: str):
    return nbf.v4.new_markdown_cell(clean(text))


def code(text: str):
    return nbf.v4.new_code_cell(clean(text))


cells = [
    markdown(
        """
        # Chapter 10: Shipping the Thing

        **Deployment patterns and infrastructure — a runnable learning walkthrough**

        This notebook takes the maintenance planner from an engineer's virtual machine to a governed release path. You will park an approval without keeping a worker alive, enforce a tool contract, name every behavior-changing input in one bundle, run the release gate locally, roll back honestly, drill six kill switches, refuse an incomplete listing, and put built, joined, assembled, and bought agents on one board.

        The walkthrough is deterministic and offline. It makes no model calls, reads no credential, and sends no telemetry.
        """
    ),
    markdown(
        """
        ## Start here

        Run the cells from top to bottom once. The sequence mirrors the chapter:

        1. Choose a runtime home and make approval waits durable.
        2. Separate immutable image inputs from runtime state and secrets.
        3. Enforce each tool's declared contract before execution.
        4. Name one release bundle and compute its canonical digest.
        5. Run the deterministic floor and evaluation gate.
        6. Move from monitor to comment to block without replacing the gate.
        7. Roll out, roll back, and name what a pointer cannot reverse.
        8. Press and drill six external kill switches.
        9. Refuse an agent listing, then let it earn a place.
        10. Route intake and read one board across all four adoption routes.
        """
    ),
    markdown("## 0. Setup"),
    code(
        """
        from __future__ import annotations

        import sys
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path

        chapter_root = Path.cwd()
        if not (chapter_root / "chapter10").exists():
            candidate = chapter_root / "chapter 10"
            if candidate.exists():
                chapter_root = candidate
        if str(chapter_root) not in sys.path:
            sys.path.insert(0, str(chapter_root))

        from chapter10.adapter import adapt_legacy_report
        from chapter10.artifacts import TEMPLATE_ROOT
        from chapter10.board import board_rows, load_board
        from chapter10.contracts import ContractEnforcer
        from chapter10.evidence import emit_deployment_evidence, verify_manifest
        from chapter10.gate import compare_reports, run_pipeline
        from chapter10.intake import recommend_route
        from chapter10.models import EvaluationReport, IntakeRequest
        from chapter10.register import run_listing_demo
        from chapter10.release import (
            ROLLBACK_LIMITS,
            ParkedRunStore,
            ReleasePointer,
            bundle_digest,
            load_bundle,
        )
        from chapter10.switches import KillSwitchMap

        work = Path(tempfile.mkdtemp(prefix="chapter10-walkthrough-"))
        print("Offline deployment harness ready; temporary output:", work)
        """
    ),
    markdown(
        """
        ## 1. Where an agent actually runs

        A production home needs a per-session sandbox, a durable state or memory service, workload identity, injected telemetry, an idle timeout beneath a hard ceiling, and limits on turns, time, and money. A managed runtime, the company's own containers, and a durable workflow engine can all provide that shape. The lock-in lives in memory, identity, and gateway configuration that exists only in a console, not in compute.

        ![What a run needs from its home](assets/figure_10_1.png)

        The worker below owns no state between turns. It parks serialized state in a server-owned store with the bundle and idempotency key. If the release moves while the planner is at lunch, the run becomes stale and restarts rather than carrying an old approval into new behavior.
        """
    ),
    code(
        """
        parked = ParkedRunStore()
        parked.park(
            run_id="run-42",
            bundle="maintenance-planner@41.3",
            state={"pending_tool": "create_work_order", "plant": "Plant D"},
            idempotency_key="work-order:Plant-D:42",
            now=datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc),
        )
        parked.resume(
            "run-42",
            current_bundle="maintenance-planner@41.4",
            approved=True,
        ).model_dump()
        """
    ),
    markdown(
        """
        A self-hosted model is another service, not a free escape from providers. Pin checkpoint digest, quantization, and serving version together. Any change to one is a model change for the gate, because formatting, stopping, and tool calls can move under quantization.
        """
    ),
    markdown(
        """
        ## 2. The box: what goes in and what stays out

        Code, exact dependency pins, skills, tool declarations, the evaluation runner, and policy files belong inside the image. Model route, prompt version, session state, sandbox mounts, gateway, and secrets arrive from outside. A secret never enters an image or context file; the deployed identity earns short-lived credentials at runtime.

        ![Image and runtime boundary](assets/figure_10_2.png)
        """
    ),
    markdown("### A tool is a service with a contract"),
    code(
        """
        contracts = ContractEnforcer.from_directory(TEMPLATE_ROOT / "contracts")
        allowed = contracts.check("parts.catalog.lookup", "get_lead_time")
        denied = contracts.check("parts.catalog.lookup", "create_order")
        missing = contracts.check("shadow.tool", "read")
        {
            "allowed": allowed.__dict__,
            "denied_before_execution": denied.__dict__,
            "undeclared_tool": missing.__dict__,
        }
        """
    ),
    markdown(
        """
        The contract version lands on the trace. A denial therefore reads as a control tripping, not as the model declining to act. The checked-in contract accepts only workload identity, declares egress, and keeps read operations disjoint from its never list.
        """
    ),
    markdown(
        """
        ## 3. One hash to ship it

        The bundle names every input that can change behavior: image and sandbox digests, prompt, catalog, policy, primary and fallback model pins, memory compatibility, and evaluation suite. A model change is a release. A fallback earns its place before an outage sends traffic to it.

        ![Release bundle](assets/figure_10_3.png)
        """
    ),
    code(
        """
        release = load_bundle(TEMPLATE_ROOT / "bundle.yaml")
        {
            "bundle": release.bundle,
            "canonical_sha256": bundle_digest(release),
            "image_is_digest_pinned": "@sha256:" in release.image,
            "fallback_earned_release": (
                release.model.fallback.golden_pass >= release.model.fallback.floor
            ),
            "memory_reads": release.memory_schema.reads,
        }
        """
    ),
    markdown(
        """
        ### Make the gate a rule

        The local pipeline runs four checks: the deterministic secret floor, contract validation, repeated evaluation against the baseline, and provenance binding to the bundle digest. A git-host ruleset, not the evaluation library, makes its named status required.
        """
    ),
    code(
        """
        pipeline = run_pipeline(
            TEMPLATE_ROOT,
            mode="block",
            output_path=work / "pipeline-report.json",
        )
        {
            "passed": pipeline.passed,
            "gate": pipeline.gate.model_dump(),
            "stages": [stage.model_dump() for stage in pipeline.stages],
        }
        """
    ),
    markdown(
        """
        A release result cannot come from cached model answers. Required cases use pass-to-the-k: all trials must pass. The comparison uses Wilson intervals rather than failing on a one-point fluctuation.

        The enforcement ladder is operational policy around one decision. `monitor` records what would happen. `comment` gives the team a visible, non-blocking finding. `block` turns the same failure into a held release.
        """
    ),
    code(
        """
        baseline = EvaluationReport(
            suite="golden@test",
            bundle="planner@old",
            passed=95,
            total=100,
            floor=0.85,
            trials_per_case=5,
            required_case_trials_passed=5,
        )
        regression = EvaluationReport(
            suite="golden@test",
            bundle="planner@new",
            passed=72,
            total=100,
            floor=0.85,
            trials_per_case=5,
            required_case_trials_passed=5,
        )
        {
            mode: compare_reports(regression, baseline, mode=mode).model_dump()
            for mode in ("monitor", "comment", "block")
        }
        """
    ),
    markdown(
        """
        ### Roll out, roll back, and do not lie about either

        The golden path builds, attests, and signs the image, writes the bundle, moves one plant to the new pointer, and watches the new slice. Shadow mode runs the candidate beside the current bundle and discards its actions.

        ![Golden release path](assets/figure_10_4.png)
        """
    ),
    code(
        """
        pointer = ReleasePointer("maintenance-planner@41.2")
        pointer.move("maintenance-planner@41.3")
        rolled_back_to = pointer.rollback()
        {"pointer": rolled_back_to, "rollback_cannot_undo": ROLLBACK_LIMITS}
        """
    ),
    markdown(
        """
        ## 4. Pulling the plug

        There are six switches because each stops something different. Gateway budget zero stops model calls. Identity disablement stops actions. A contract change removes one scope. The runtime pointer stops new runs. Register suspension stops discovery. Data decertification stops an unsafe supply. Each switch belongs to an owner and a different backup outside the builder team.

        ![Six kill switches](assets/figure_10_5.png)
        """
    ),
    code(
        """
        switches = KillSwitchMap("maintenance-planner")
        plant_d = switches.press("identity", target="Plant D")
        switches.reset("identity")
        {
            "tenant_specific_press": plant_d.model_dump(),
            "quarterly_staging_drill": [result.model_dump() for result in switches.drill_all()],
        }
        """
    ),
    markdown(
        """
        ## 5. The platform at full size

        Every agent on the path has an identity, one gateway, approved tools under contracts, a release gate, and tracing outside its control. The sixth item is the register entry that makes those controls visible across vendors and frameworks.

        ![Platform harness](assets/figure_10_6.png)
        """
    ),
    markdown("### The listing gate says what done means"),
    code(
        """
        first, second = run_listing_demo(work / "listing-demo")
        {
            "first_attempt": first.model_dump(),
            "after_required_evidence_exists": second.model_dump(),
        }
        """
    ),
    markdown(
        """
        The first attempt is registered—a name and owner exist—but not listed. High-tier listing requires a tier record, uncached evaluation under the current bundle, security review, oversight note, and configuration reference. The second attempt earns visibility without a human remembering those joins on Friday afternoon.
        """
    ),
    markdown(
        """
        ### Intake before build

        Intake asks what the agent does, for whom, who reviews it, which data it touches, and whether something already does the job. The cheapest safe agent is often one the company already runs or a product it already buys.

        ![Intake funnel](assets/figure_10_7.png)
        """
    ),
    code(
        """
        requests = [
            IntakeRequest(
                name="plant maintenance work-order helper",
                purpose="draft work orders from plant sensor readings",
                audience="planners",
                reviewer="planner",
                data_tier="high",
                workflow_kind="company-specific",
                needs_internal_inspection=True,
            ),
            IntakeRequest(
                name="calendar helper",
                purpose="schedule internal meetings",
                audience="staff",
                reviewer="signed-in user",
                data_tier="low",
                workflow_kind="commodity",
                needs_internal_inspection=False,
            ),
            IntakeRequest(
                name="alloy optimizer",
                purpose="recommend furnace settings",
                audience="process engineers",
                reviewer="process engineer",
                data_tier="high",
                workflow_kind="company-specific",
                needs_internal_inspection=True,
            ),
        ]
        [recommend_route(request).model_dump() for request in requests]
        """
    ),
    markdown(
        """
        ## 6. Four ways in, one shared gate

        Build starts on the template path. Join imports one stage in monitor mode and adapts the team's existing suite instead of replacing it. Assemble starts from intake with identity, budget, contracts, and an empty golden set. Buy turns missing observability, change notice, test tenant, and usage export into contract lines.

        ![Four routes onto the path](assets/figure_10_8.png)
        """
    ),
    code(
        """
        legacy = adapt_legacy_report(
            {
                "successes": 87,
                "cases": 100,
                "suite_version": "invoice-suite@12",
                "tokens": 44000,
            },
            bundle="invoice-triage@18.2",
            floor=0.85,
        )
        {
            "joined_suite": legacy.model_dump(),
            "pass_rate": legacy.pass_rate,
            "required_common_fields": [
                "pass rate",
                "floor",
                "bundle",
                "suite version",
                "tokens",
            ],
        }
        """
    ),
    markdown(
        """
        ## 7. Four agents, one board

        Progress is a state rather than a promised date. Quality comes from the evaluator appropriate to each route. Cost remains visibly `metered` or `allocated`. Missing vendor signals say `not observable` or `not reading`; an empty cell never pretends the evidence exists.

        ![Four-agent operating board](assets/figure_10_9.png)
        """
    ),
    code(
        """
        rows = board_rows(load_board())
        rows
        """
    ),
    markdown("### Export one reviewable evidence pack"),
    code(
        """
        evidence_dir = work / "deployment-evidence"
        summary = emit_deployment_evidence(evidence_dir)
        {
            "summary": summary,
            "manifest_verified": verify_manifest(evidence_dir),
            "files": sorted(
                str(path.relative_to(evidence_dir))
                for path in evidence_dir.rglob("*")
                if path.is_file()
            ),
        }
        """
    ),
    markdown(
        """
        ## What you have built

        The maintenance planner now has a home that is not a person's virtual machine, a release identity that names every behavior-changing input, a gate the git host can enforce, an approval wait that survives a worker, six external stop controls, and evidence that earns its register listing. The same path accepts a mature service, an editor-assembled agent, and a bought product without pretending their evidence sources are identical.

        The companion deliberately stops at the platform boundary. Replace the local files with the organization's durable workflow store, workload identity, gateway, artifact registry, git ruleset, telemetry pipe, certified data catalog, and incident system while preserving these contracts.
        """
    ),
]

notebook = nbf.v4.new_notebook()
notebook["cells"] = cells
notebook["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}
nbf.write(notebook, OUTPUT)
print(f"Wrote {OUTPUT}")
