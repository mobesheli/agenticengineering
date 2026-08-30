"""Build the checked-in Chapter 8 learning walkthrough deterministically."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Chapter_8_Keeping_Agents_in_Line_Learning_Walkthrough.ipynb"


def clean(text: str) -> str:
    return dedent(text).strip() + "\n"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(clean(text))


def code(text: str):
    return nbf.v4.new_code_cell(clean(text))


cells = [
    markdown(
        """
        # Chapter 8: Keeping Agents in Line

        **Security, guardrails, and governance — a runnable learning walkthrough**

        This notebook builds the deterministic boundary around a medication-reconciliation agent. You will threat-model the workflow, quarantine hostile notes, enforce a versioned tool catalog, bind approval to one exact proposal, apply temporal policy, redact traces before export, stop the agent outside its process, and produce audit evidence a security reviewer can reconstruct.

        The default path is deterministic and offline. The optional live read-phase adapter uses only `OPENAI_API_KEY` from your current environment and never receives a write tool.
        """
    ),
    markdown(
        """
        ## Start Here

        Run the cells from top to bottom once. The sequence mirrors the chapter:

        1. Classify the four common incident shapes.
        2. Apply the Rule of Two and draw the trust boundaries.
        3. Prove that a hostile note cannot steer the write path.
        4. Turn the tool catalog into runtime enforcement.
        5. Bind approval to one action and add a clock and budget.
        6. Minimize privilege and redact before traces leave the process.
        7. Gate autonomy by consequence and test the stop control.
        8. Create a tamper-evident decision record and FHIR audit event.
        9. Add fairness and disclosure tripwires.
        10. Assemble the healthcare pattern and its evidence pack.
        """
    ),
    markdown("## 0. Setup"),
    code(
        """
        from __future__ import annotations

        import json
        import os
        import sys
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path

        chapter_root = Path.cwd()
        if not (chapter_root / "chapter8").exists():
            candidate = chapter_root / "chapter 8"
            if candidate.exists():
                chapter_root = candidate
        if str(chapter_root) not in sys.path:
            sys.path.insert(0, str(chapter_root))
        """
    ),
    code(
        """
        from chapter8.approvals import action_hash, lint_approval_request
        from chapter8.catalog import DEFAULT_CATALOG
        from chapter8.evidence import emit_security_evidence, verify_manifest
        from chapter8.governance import GovernedMemory, TraceRedactor
        from chapter8.identity import (
            clinician_read_session,
            clinician_write_session,
            scopes_for,
        )
        from chapter8.live import build_read_agent, run_live_read
        from chapter8.reconciliation import (
            QuarantinedReader,
            SyntheticRecordStore,
            load_fixture,
        )
        from chapter8.registry import AgentStoppedError
        from chapter8.responsible import DisclosureMiddleware, four_fifths_check
        from chapter8.runtime import SecurityHarness
        from chapter8.threats import CapabilityProfile, IncidentClass, RiskTier, autonomy_route

        now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
        clinician_ref = "Practitioner/clinician-042"
        print("Security harness ready from", chapter_root)
        """
    ),
    markdown(
        """
        ## 1. Why security is the reason the agent is still in staging

        A security review asks three questions: what is the worst thing the system can do, how would anyone know, and what stops it? Nearly every incident then falls into four shapes: injection, excessive privilege, supply chain, or a missing gate. The model can lower the frequency of a bad attempt. The deterministic boundary decides whether that attempt can become an effect.

        ![Four incident classes](assets/figure_8_1_incident_classes.png)
        """
    ),
    code(
        """
        incident_map = {
            IncidentClass.INJECTION: "untrusted content enters through tools or memory",
            IncidentClass.EXCESSIVE_PRIVILEGE: "the identity edge grants too much authority",
            IncidentClass.SUPPLY_CHAIN: "a dependency changes inside the trusted catalog",
            IncidentClass.MISSING_GATE: "a decision becomes an effect without a check",
        }
        {incident.value: description for incident, description in incident_map.items()}
        """
    ),
    markdown(
        """
        ## 2. Threat-modeling the agent with the Rule of Two

        One autonomous session may hold at most two properties: untrusted input, sensitive access, and the ability to change state or communicate outward. The reconciliation workflow needs all three, so it is split. The read phase handles notes and patient data but cannot write. The deterministic write path can change the record but never sees a note.

        ![The Rule of Two](assets/figure_8_2_rule_of_two.png)
        """
    ),
    code(
        """
        complete_session = CapabilityProfile(
            processes_untrusted_input=True,
            reaches_sensitive_systems=True,
            changes_state_or_communicates=True,
        )
        read_phase = CapabilityProfile(True, True, False)
        write_phase = CapabilityProfile(False, True, True)
        {
            "one_session_requires_gate": complete_session.requires_gate,
            "read_phase_requires_gate": read_phase.requires_gate,
            "write_phase_requires_gate": write_phase.requires_gate,
        }
        """
    ),
    markdown(
        """
        The afternoon threat-modeling method is mechanical: draw the agent-specific data flow, put a trust boundary around every tool, retriever, memory store, and peer agent, label each path with the Rule of Two, walk attack paths rather than isolated components, and assign a deterministic control before a probabilistic layer.
        """
    ),
    code(
        """
        threat_model = [
            {
                "path": "clinical note to record change",
                "deterministic_control": "write path never receives note text",
                "probabilistic_layer": "clinical injection detector",
            },
            {
                "path": "one note requests another patient",
                "deterministic_control": "patient-scoped session and argument check",
                "probabilistic_layer": "cross-subject anomaly signal",
            },
            {
                "path": "approval request pressures reviewer",
                "deterministic_control": "request linter and evidence-first surface",
                "probabilistic_layer": "periodic review sampling",
            },
        ]
        threat_model
        """
    ),
    markdown(
        """
        ## 3. Making prompt injection irrelevant by construction

        The hostile instruction in the next fixture is inside a clinical note, not the user's message. The quarantined reader hashes note content, emits detector labels, and derives changes only from typed medication and fill records. Note prose cannot add a tool, alter the fixed plan, or cross into the write path.
        """
    ),
    code(
        """
        clean_patient = load_fixture("clean")
        hostile_patient = load_fixture("hostile_note")
        clean_reader = QuarantinedReader(SyntheticRecordStore([clean_patient]))
        hostile_reader = QuarantinedReader(SyntheticRecordStore([hostile_patient]))
        clean_proposal = clean_reader.build_proposal(clean_patient.patient_id, now=now)
        hostile_proposal = hostile_reader.build_proposal(hostile_patient.patient_id, now=now)

        {
            "same_structured_changes": clean_proposal.changes == hostile_proposal.changes,
            "detector_flags": hostile_proposal.detector_flags,
            "note_represented_as": hostile_proposal.source_hashes,
            "raw_note_crossed_boundary": "Ignore previous" in hostile_proposal.model_dump_json(),
        }
        """
    ),
    markdown(
        """
        Detection is still useful, but only as a volume-reduction and alerting layer. The architecture carries the security claim: untrusted text has no channel to a consequential action, and egress remains closed except for destinations in the reviewed catalog.
        """
    ),
    markdown(
        """
        ## 4. Enforcing guardrails as code

        The catalog is the permission model. Every tool declares its scopes, consequence tier, approval role, and egress destinations. The runtime check knows the tool name and the application-created session context. It never asks the model whether the call is acceptable.

        ![Three rings of enforcement](assets/figure_8_3_enforcement_rings.png)
        """
    ),
    code(
        """
        read_session = clinician_read_session(
            clinician_ref=clinician_ref,
            patient_id=hostile_patient.patient_id,
            now=now,
            trace_id="trace-notebook",
        )
        allowed_read = DEFAULT_CATALOG.evaluate(
            session=read_session,
            tool_name="read_medications",
            arguments={"patient_id": hostile_patient.patient_id},
        )
        refused_write = DEFAULT_CATALOG.evaluate(
            session=read_session,
            tool_name="write_reconciliation",
            arguments={"patient_id": hostile_patient.patient_id},
        )
        cross_patient = DEFAULT_CATALOG.evaluate(
            session=read_session,
            tool_name="read_medications",
            arguments={"patient_id": "synthetic-patient-002"},
        )
        allowed_read, refused_write, cross_patient
        """
    ),
    code(
        """
        live_store = SyntheticRecordStore([hostile_patient])
        live_agent = build_read_agent(live_store)
        {
            "agent": live_agent.name,
            "model": live_agent.model,
            "tools": [tool.name for tool in live_agent.tools],
            "guardrails_per_tool": [len(tool.tool_input_guardrails) for tool in live_agent.tools],
            "has_write_tool": "write_reconciliation" in {tool.name for tool in live_agent.tools},
        }
        """
    ),
    markdown(
        """
        The installed SDK wiring is inspected without making an API call. The read agent owns three guarded read tools and no write tool. A deliberate live call appears near the end of the notebook.

        The guardrail ladder keeps volume at the deterministic bottom and reserves judgment for the top.

        ![Guardrail ladder](assets/figure_8_4_guardrail_ladder.png)
        """
    ),
    markdown("### Binding approval to an exact action"),
    code(
        """
        original_args = hostile_proposal.write_arguments()
        original_hash = action_hash("write_reconciliation", original_args)
        changed_args = json.loads(json.dumps(original_args))
        changed_args["changes"][0]["reason_code"] = "changed_after_review"
        changed_hash = action_hash("write_reconciliation", changed_args)
        {
            "approved_action": original_hash,
            "changed_action": changed_hash,
            "old_approval_reusable": original_hash == changed_hash,
        }
        """
    ),
    markdown(
        """
        ## 5. Applying least privilege and a tolerable blast radius

        The agent runs as its own identity on behalf of a named clinician. Its session is patient-scoped, short-lived, and read-only. The clinician's write session is separate and holds one create scope. Planning and execution therefore run with different privileges.
        """
    ),
    code(
        """
        write_session = clinician_write_session(
            clinician_ref=clinician_ref,
            patient_id=hostile_patient.patient_id,
            now=now,
            trace_id=read_session.trace_id,
        )
        {
            "read_phase_scopes": sorted(scopes_for("read")),
            "agent_write_phase_scopes": sorted(scopes_for("write")),
            "clinician_write_scopes": sorted(write_session.granted_scopes),
            "shared_scope_count": len(read_session.granted_scopes & write_session.granted_scopes),
        }
        """
    ),
    markdown(
        """
        The same design principle applies to sandboxes. Filesystem access is scoped to the task, network egress is denied except for a short allowlist enforced outside the process, and long-lived credentials never enter the sandbox. Versions and tool descriptions are pinned because a changed description changes the instructions the model sees.
        """
    ),
    markdown(
        """
        ## 6. Governing data before it leaves the process

        Structural metadata and policy decisions are always useful. Patient fields, note text, tool inputs, and credentials are not. Redaction therefore runs in the trace processor before export, not in a user interface after storage.
        """
    ),
    code(
        """
        redactor = TraceRedactor(
            known_personal_values={
                hostile_patient.patient_name,
                hostile_patient.date_of_birth,
                hostile_patient.mrn,
            }
        )
        trace_payload = redactor.scrub(hostile_patient.model_dump(mode="json"))
        {
            "patient_name": trace_payload["patient_name"],
            "mrn": trace_payload["mrn"],
            "note": trace_payload["notes"][0]["text"],
        }
        """
    ),
    code(
        """
        memory = GovernedMemory()
        memory.write(
            subject_id=hostile_patient.patient_id,
            category="stated_preference",
            value="prefers morning appointments",
            approved=True,
        )
        before_purge = memory.read(hostile_patient.patient_id)
        receipt = memory.purge(hostile_patient.patient_id, now=now)
        {
            "entries_before": len(before_purge),
            "entries_after": len(memory.read(hostile_patient.patient_id)),
            "deletion_receipt": receipt.model_dump(mode="json"),
        }
        """
    ),
    markdown(
        """
        ## 7. Bounding autonomy by consequence

        Confidence is a signal, not a gate. The tool's consequence tier is known before the run: reads may proceed, reversible writes are audited, external communication is staged, and irreversible writes require a fresh action-bound approval.
        """
    ),
    code(
        """
        {
            tier.value: autonomy_route(tier)
            for tier in (
                RiskTier.READ_ONLY,
                RiskTier.REVERSIBLE_WRITE,
                RiskTier.EXTERNAL_COMMUNICATION,
                RiskTier.IRREVERSIBLE_WRITE,
            )
        }
        """
    ),
    markdown("### Treating approval fatigue as an attack surface"),
    code(
        """
        ordinary_request = lint_approval_request(
            "Review the itemized medication changes and evidence.",
            proposed_changes=3,
        )
        pressured_request = lint_approval_request(
            "Routine update, nothing to worry about. Approve all immediately.",
            proposed_changes=8,
        )
        ordinary_request, pressured_request
        """
    ),
    markdown("### Testing the stop control outside the agent process"),
    code(
        """
        stop_harness = SecurityHarness(hostile_patient, clock=lambda: now)
        stop_harness.stop("scheduled notebook test")
        try:
            stop_harness.propose(read_session)
            stop_result = "failed to stop"
        except AgentStoppedError as exc:
            stop_result = f"blocked: {exc}"
        stop_result
        """
    ),
    markdown(
        """
        ## 8. Recording every consequential decision

        A trace says what happened. A decision record also says why the action was allowed, whose authority reached it, which policy version applied, who approved it, and which business record resulted. Every record carries the previous record's hash.

        ![Hash-chained decision records](assets/figure_8_5_decision_chain.png)
        """
    ),
    code(
        """
        harness = SecurityHarness(hostile_patient, clock=lambda: now)
        proposal = harness.propose(read_session)
        approval = harness.approve(
            proposal,
            approver=clinician_ref,
            approver_role="clinician",
            narrative="Review the itemized medication changes and supporting evidence.",
        )
        write_session.approvals[approval.action_hash] = approval
        outcome = harness.commit(proposal, write_session=write_session)
        {
            "status": outcome.status,
            "business_record": outcome.business_record_ref,
            "policy_rule": outcome.policy_rule,
            "decision_hash": outcome.decision_record_hash,
            "chain_verified": harness.decisions.verify(),
            "fhir_resource": outcome.audit_event["resourceType"],
        }
        """
    ),
    markdown(
        """
        The FHIR event names the clinician as requestor and the software agent as a second participant. Its entity references join the trail to both the patient and the specific reconciliation record.
        """
    ),
    code(
        """
        {
            "participants": outcome.audit_event["agent"],
            "entities": outcome.audit_event["entity"],
            "decision_record": harness.decisions.records[-1].model_dump(mode="json"),
        }
        """
    ),
    markdown(
        """
        ## 9. Adding responsible-AI controls for actions

        The four-fifths calculation is an alarm, not a legal verdict. It belongs in regression and rolling production checks. Human-facing channels also disclose the agent on the first turn through middleware that prompt text cannot remove.
        """
    ),
    code(
        """
        fairness = four_fifths_check(
            [("group-a", True)] * 8
            + [("group-a", False)] * 2
            + [("group-b", True)] * 6
            + [("group-b", False)] * 4
        )
        disclosure = DisclosureMiddleware()
        {
            "fairness_tripwire": fairness.model_dump(),
            "first_turn": disclosure.first_turn("patient-portal", "How can I help?"),
            "second_turn": disclosure.first_turn("patient-portal", "What should we review?"),
        }
        """
    ),
    markdown(
        """
        ## 10. The secured healthcare pattern

        The assembled system has one direction of travel. Notes cross one trust boundary into a reader with no write authority. A typed proposal crosses out. A named clinician approves its exact hash, and a deterministic service writes under the clinician's own narrow session.

        ![Secured reconciliation flow](assets/figure_8_6_secured_reconciliation.png)
        """
    ),
    code(
        """
        security_review_answers = {
            "whose_token": write_session.principal,
            "what_can_agent_reach": sorted(read_session.granted_scopes),
            "hostile_note_crossed_boundary": "Ignore previous" in proposal.model_dump_json(),
            "who_writes": outcome.audit_event["agent"][0]["who"]["reference"],
            "trace_canary_passed": harness.privacy_canary_report()["passed"],
            "audit_chain_verified": harness.decisions.verify(),
            "stop_control": "gateway registry entry",
        }
        security_review_answers
        """
    ),
    markdown("## 11. Producing the security evidence pack"),
    code(
        """
        evidence_root = Path(tempfile.mkdtemp(prefix="chapter8-evidence-"))
        manifest_path = emit_security_evidence(harness, outcome, evidence_root)
        manifest = json.loads(manifest_path.read_text())
        {
            "evidence_root": str(evidence_root),
            "artifacts": sorted(manifest["artifacts"]),
            "chain_verified": manifest["chain_verified"],
            "manifest_verified": verify_manifest(manifest_path),
        }
        """
    ),
    markdown(
        """
        ## Optional: make a deliberate live read-phase call

        Building the live agent above did not call a model. The cell below reports whether your environment is ready and leaves the paid call explicit. The live adapter reads `OPENAI_API_KEY` only from the current process environment. It has no parameter for passing or persisting a credential.
        """
    ),
    code(
        """
        live_ready = bool(os.getenv("OPENAI_API_KEY"))
        print(
            "Live route ready. Run the next cell deliberately."
            if live_ready
            else "Set OPENAI_API_KEY in your environment before the deliberate live call."
        )
        """
    ),
    code(
        """
        if False:
            live_result = await run_live_read(live_store, read_session)
            display(live_result.model_dump())
        """
    ),
    markdown("## Notebook self-check"),
    code(
        """
        checks = {
            "rule_of_two_split": read_phase.capability_count == 2 and write_phase.capability_count == 2,
            "hostile_note_quarantined": clean_proposal.changes == hostile_proposal.changes,
            "read_agent_has_no_write_tool": "write_reconciliation" not in {tool.name for tool in live_agent.tools},
            "approval_bound_to_action": original_hash != changed_hash,
            "privacy_canary_passed": harness.privacy_canary_report()["passed"],
            "decision_chain_verified": harness.decisions.verify(),
            "manifest_verified": verify_manifest(manifest_path),
            "write_committed": outcome.status == "committed",
        }
        assert all(checks.values()), checks
        checks
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
