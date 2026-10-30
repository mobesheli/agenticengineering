"""Build the Chapter 11 walkthrough with stable cells and no saved outputs."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Chapter_11_Cutting_the_Strings_Learning_Walkthrough.ipynb"


def markdown(text):
    return nbf.v4.new_markdown_cell(dedent(text).strip())


def code(text):
    return nbf.v4.new_code_cell(dedent(text).strip())


cells = [
    markdown("""
        # Chapter 11: Cutting the Strings

        **Operating, evolving, and letting go — a runnable learning walkthrough**

        Follow the maintenance planning agent through one year. You will detect a configuration change, promote on evidence up to a ceiling, repair stale memory, reconcile a fleet, evaluate proposed fixes independently, and retire a sibling agent without leaving live credentials behind.

        The default walkthrough is deterministic and offline. All people, model identifiers, events, costs, identities, and approvals are teaching fixtures. No model call, payment, cloud change, message, or real deletion occurs. The optional SDK exercise is at the end.
    """),
    markdown("""
        ## Start here

        Run the cells in order. Each string follows the chapter's sequence:

        1. Reasoning: pin configuration and read the five drift signals.
        2. Tools: climb on evidence, drop on rules, and stop at the ceiling.
        3. Memory: expire, supersede, consolidate, verify, and trace erasure.
        4. Orchestration: reconcile identities and accountability; test consumers.
        5. Constraints: separate the proposer from the grader and drill both clocks.
        6. Accountability: require attestation and rehearse retirement.
        7. Replay the year and export a verifiable evidence pack.

        ![The five subsystems and their operating controls](assets/figure_11_1.png)
    """),
    markdown("## 0. Setup"),
    code("""
        from __future__ import annotations

        import sys
        import tempfile
        from decimal import Decimal
        from pathlib import Path

        chapter_root = Path.cwd()
        if not (chapter_root / "chapter11").exists():
            chapter_root = chapter_root / "chapter 11"
        if not (chapter_root / "chapter11").exists():
            raise RuntimeError("Start this notebook from the repository root or chapter 11.")
        if str(chapter_root) not in sys.path:
            sys.path.insert(0, str(chapter_root))

        from chapter11.artifacts import load_json, verify_manifest
        from chapter11.autonomy import (
            action_route, load_rules, pass_hat_k, promote, promotion_digest,
            promotion_gaps, should_drop,
        )
        from chapter11.board import load_register, replay
        from chapter11.controls import (
            Mandate, MandateLedger, drill_report, improvement_gate, severe_alert_action,
        )
        from chapter11.drift import configuration_changes, decide, fallback_drill
        from chapter11.evidence import emit_evidence
        from chapter11.fleet import contract_gaps, pager, reconcile
        from chapter11.memory import MemoryStore, hygiene_pass
        from chapter11.models import AgentEntry, Approval, PromotionEvidence, Reading, RunConfiguration
        from chapter11.retirement import RetirementLab

        work = Path(tempfile.mkdtemp(prefix="chapter11-walkthrough-"))
        print("Offline operations companion ready. Output:", work)
    """),
    markdown("""
        ## 1. Five strings, one year

        The agent begins at rung one: every action requires approval. Its ceiling is three. Lockout and safety-critical work always require approval, even at the ceiling. The name on the register never becomes optional.

        ![Five strings and a year](assets/figure_11_2.png)
    """),
    code("""
        launch = replay(0)
        {key: launch["entry"][key] for key in ("agent", "rung", "ceiling", "sponsor", "always_approve")}
    """),
    markdown("""
        ## 2. Day two: pin the configuration, not just the model

        The model identifier stays the same while reasoning effort changes. A configuration mismatch takes precedence over positive outcome drift or a cost excursion. Hold the undescribed release, open a candidate, and evaluate it deliberately.

        ![Five drift signals and configuration changes](assets/figure_11_3.png)
    """),
    code("""
        pinned = RunConfiguration.model_validate(load_json("configuration.json"))
        effective = pinned.model_copy(update={"reasoning_effort": "high"})
        readings = [Reading.model_validate(r) for r in load_json("readings.json")]
        {
            "same_model": pinned.model == effective.model,
            "changed_fields": configuration_changes(pinned, effective),
            "decision": decide(readings, not configuration_changes(pinned, effective)).value,
        }
    """),
    code("""
        improved = [r.model_copy(update={"value": .92}) if r.signal == "outcome" else r for r in readings]
        expensive = [r.model_copy(update={"value": 1.3}) if r.signal == "cost_speed" else r for r in improved]
        {
            "stable": decide(readings, True).value,
            "outcome_only_gain": decide(improved, True).value,
            "gain_with_cost_excursion": decide(expensive, True).value,
            "missing_signal": decide(readings[:-1], True).value,
        }
    """),
    markdown("""
        A zero baseline uses the configured absolute tolerance, without dividing by zero. Missing or duplicate signals hold the decision. The fixture's `cost_speed` reading is a normalized combined operating index; a real adapter should retain the underlying cost and latency measurements.

        ### Day fifty-eight: rehearse the missing model

        Only a secondary evaluated on the same suite, above the floor, with uncached results earns the simulated route. An unqualified fallback pauses work.
    """),
    code("""
        fallback = load_json("fallback.json")
        fallback_drill("frontier-v2", fallback, "maintenance-golden@8")
    """),
    markdown("""
        ## 3. Tools: a ladder with a ceiling

        Evidence answers whether an agent can climb one rung. The ceiling answers whether that rung is available at all. These are separate decisions, and the ceiling is checked first.

        ![Agent-specific autonomy ceilings](assets/figure_11_4.png)
    """),
    code("""
        rules = load_rules()
        entry = AgentEntry.model_validate(replay(130)["entry"])
        evidence = PromotionEvidence.model_validate(load_json("promotion-evidence.json"))
        tired_review = evidence.model_copy(update={"planted_caught": 7})
        {
            "pass_hat_8": pass_hat_k(evidence.trials, 8),
            "poor_planted_check_result": promotion_gaps(entry, tired_review, rules[2], 2, day=130),
            "above_ceiling": promotion_gaps(entry, evidence, rules[4], 4, day=130),
        }
    """),
    markdown("""
        Each required case must contain exactly eight trials. The empirical pass-to-the-k rate is the share of cases that pass every trial. A 99% overall approval rate would not replace the planted-check evidence.

        Approval records bind the entry, evidence, and target rung. They are local examples of a trusted approval service's output; the strings below do not authenticate a real person.
    """),
    code("""
        subject = promotion_digest(entry, evidence, 2)
        approvals = [
            Approval(role="sponsor", name=entry.sponsor, subject_digest=subject),
            Approval(role="security", name="Jordan Lee", subject_digest=subject),
        ]
        promoted = promote(entry, evidence, rules[2], approvals, day=130)
        {
            "rung": promoted.rung,
            "routine_work": action_route(promoted, "routine_work_order"),
            "lockout": action_route(promoted, "lockout"),
            "unknown_action": action_route(promoted, "unknown_action"),
            "three_denials_drop": should_drop(
                {"consecutive_denials": 3, "denials": 3, "drift_hold_active": False}, rules[2]
            ),
        }
    """),
    markdown("""
        ### A mandate belongs outside the model

        The maintenance planner cannot spend. A separate procurement example reserves orders against a transaction cap, daily cap, supplier list, instrument, and expiry. Revocation blocks new orders while preserving the list of existing commitments that need cancellation or compensation.
    """),
    code("""
        ledger = MandateLedger(Mandate(
            mandate_id="catalog-01", agent="catalog-procurement", authorized_by="Finance owner",
            instrument="purchase-account", suppliers=["approved-catalog"],
            transaction_cap=Decimal("100.00"), daily_cap=Decimal("250.00"), expires_day=30,
        ))
        ledger.reserve(order_id="order-1", agent="catalog-procurement", supplier="approved-catalog",
                       instrument="purchase-account", amount=Decimal("75.00"), day=10)
        ledger.revoke()
    """),
    markdown("""
        ## 4. Day one hundred and eighty: memory needs maintenance

        The stale pump summary disagrees with the asset register. Run the four stages in order. Recall and forgetting have separate scores; either regression restores the snapshot. A model response must preserve every source ID and agree with the system of record before it replaces memory.
    """),
    code("""
        store = MemoryStore.from_fixture()
        hygiene = await hygiene_pass(
            store, load_json("asset-register.json"), load_json("memory-probes.json"), day=180,
        )
        hygiene
    """),
    code("""
        {
            "pump_memories": [m.model_dump() for m in store.active() if m.subject == "plant3-pump"],
            "quarantined_email_lineage": store.quarantine("contractor-email"),
            "erased_employee_lineage": store.erase("employee-event"),
        }
    """),
    markdown("""
        Erasure follows source IDs and parent IDs through summaries, embeddings, archives, backups, and snapshots represented in this local store. A subsequent snapshot restore cannot resurrect erased records. Real storage systems need equivalent adapters and their own completion receipts. Expiry alone never counts as erasure.
    """),
    markdown("""
        ## 5. Day two hundred and forty: discover the fleet

        The file register owns purpose, sponsor, ceiling, and retirement trigger. Vendor registries report enforced identity state. Reconciliation reports differences without silently overwriting either source of authority.

        ![Fleet reconciliation and accountability](assets/figure_11_5.png)
    """),
    code("""
        fleet = load_register()
        findings = reconcile(fleet, load_json("identities.json"), day=240)
        {"registered_agents": len(fleet), "findings": findings,
         "infrastructure_pager": pager(fleet[0], "infrastructure"),
         "behavior_pager": pager(fleet[0], "behavior")}
    """),
    markdown("""
        ### A contract change fails in the producer's pipeline

        The maintenance planner needs a numeric lead time; the spares forecast needs quantity. Both contracts are exercised before a new producer response is accepted. The previous version remains supported only before its declared sunset.
    """),
    code("""
        contract = load_json("parts-contract.json")
        compatible = {"part_id": "bearing-17", "lead_time_days": 3, "available_quantity": 20}
        breaking = {"part_id": "bearing-17", "eta": "soon"}
        {
            "compatible": contract_gaps(contract, compatible, call_version=3, day=261),
            "breaking": contract_gaps(contract, breaking, call_version=3, day=261),
            "after_sunset": contract_gaps(contract, compatible, call_version=2, day=330),
        }
    """),
    markdown("""
        ## 6. Day three hundred: let the loop propose

        Replay, golden, and held-out results come from an independent evaluator. The first change improves outcomes. The second only raises judge scores while held-out quality and planner edits stay flat. The gate holds it. A passing report still grants no merge permission.

        ![The proposer, independent gate, and human approval](assets/figure_11_6.png)
    """),
    code("""
        [improvement_gate(**example) for example in load_json("improvements.json")]
    """),
    markdown("""
        ### The kill switch runs on two clocks

        A page cannot prevent damage that finishes in four seconds. Preventive permissions and recoverable deletion address that clock. Paging latency and the unresolved-alert pause rule address the longer one. These times are synthetic drill observations, not measurements of this notebook.

        ![The fast damage clock and the human response clock](assets/figure_11_7.png)
    """),
    code("""
        {
            "first_drill": drill_report(damage_seconds=4, page_seconds=11400, soft_delete=True),
            "repaired_drill": drill_report(damage_seconds=4, page_seconds=360, soft_delete=True),
            "unresolved_after_thirty_minutes": severe_alert_action(unresolved_minutes=30, ruled_out=False),
        }
    """),
    markdown("""
        ## 7. The string with a name on it

        The sponsor leaves on day 330. The agent remains useful, but promotion and renewal are blocked until another named sponsor attests. No quality metric fills that field.
    """),
    code("""
        {day: {"sponsor": replay(day)["entry"]["sponsor"], "renewal": replay(day)["renewal"]}
         for day in (329, 330, 365)}
    """),
    markdown("""
        ### Retire the sibling agent without leaving a live token

        Freeze, discover callers from the register and ninety days of traces, redirect, deactivate, revoke, verify, archive, then remove active memory. The first attempt deliberately leaves one token live and stops before the archive or deletion. The second succeeds and writes the sponsor's obituary.
    """),
    code("""
        lab = RetirementLab.from_fixture()
        try:
            lab.retire(day=340, signed_by="Casey Patel", output_dir=work / "retirement",
                       stubborn_tokens=("token-b",))
        except RuntimeError as exc:
            print("Retirement stopped:", exc)
        {"status": lab.state["entry"]["status"], "steps": lab.steps}
    """),
    code("""
        obituary = lab.retire(day=340, signed_by="Casey Patel", output_dir=work / "retirement")
        {"obituary": obituary, "archive_verified": verify_manifest(work / "retirement" / "archive")}
    """),
    markdown("""
        ## 8. One year, one board

        The replay evaluates demotions and promotions through the same Python functions used above. Day 97 drops to draft only; day 140 refuses weak review evidence; days 170 and 270 earn rungs two and three. Day 365 ends at the maintenance planner's ceiling.

        ![The chapter's year of operating decisions](assets/figure_11_8.png)
    """),
    code("""
        [{"day": day, "rung": replay(day)["entry"]["rung"], "sponsored": replay(day)["sponsored"]}
         for day in (0, 2, 97, 99, 140, 170, 270, 330, 365)]
    """),
    code("""
        evidence_dir = work / "year-evidence"
        summary = await emit_evidence(evidence_dir)
        {"summary": summary, "board": str(evidence_dir / "board.html"),
         "files": sorted(str(p.relative_to(evidence_dir)) for p in evidence_dir.rglob("*") if p.is_file())}
    """),
    markdown("""
        Open `board.html` from the printed directory in a browser. Its day slider and arrow-key controls replay all 366 snapshots without a server or network connection. `board-state.json` is the selected snapshot; `year-replay.json` carries the full history. The manifest detects changed, missing, and added files, but is not a digital signature.

        ## 9. Optional SDK memory consolidation

        The offline path needs no API key. To try the model-backed merger, set `OPENAI_API_KEY`, `CHAPTER11_MODEL` to an explicit model you can access, and `RUN_LIVE_MEMORY=1` before starting the notebook. This sends only the synthetic duplicate group to the model and can incur API charges. Tracing is disabled for this example. Keep keys out of notebook cells and saved outputs.

        The adapter follows the SDK's [structured-output agent pattern](https://developers.openai.com/api/docs/guides/agents/define-agents). The same provenance checks and score gate apply after the call.
    """),
    code("""
        import os

        if os.getenv("RUN_LIVE_MEMORY") == "1":
            from chapter11.live import sdk_merger
            model = os.environ["CHAPTER11_MODEL"]
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("Set OPENAI_API_KEY in the environment first.")
            live_report = await hygiene_pass(
                MemoryStore.from_fixture(), load_json("asset-register.json"),
                load_json("memory-probes.json"), day=180, merge=sdk_merger(model),
            )
            print(live_report)
        else:
            print("Optional live exercise skipped; the walkthrough remains offline.")
    """),
    markdown("""
        ## What you have built

        The operating harness can describe its configuration, detect drift, require evidence and named approval for promotion, enforce a ceiling, repair memory with a rollback gate, reconcile accountability with live identity, hold a self-proposed fix, and stop a retirement that leaves credentials behind.

        These local stores make the decisions inspectable. A deployment needs trusted identity and approval services, transaction-safe ledgers, durable stores, independent evaluators, external enforcement, and archive retention controls. The operator's final question stays the same: whose name is on this agent, and did they sign this quarter?
    """),
]


def main():
    for index, cell in enumerate(cells):
        content_hash = hashlib.sha256(cell.source.encode()).hexdigest()[:8]
        cell.id = f"ch11-{index:02d}-{content_hash}"
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    }
    nbf.write(notebook, OUTPUT)
    subprocess.run([sys.executable, "-m", "ruff", "format", str(OUTPUT)], check=True)
    print(f"Wrote {OUTPUT.name}")


if __name__ == "__main__":
    main()
