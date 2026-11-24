"""Generate the evaluation results, the register, and the evidence records.

    python scripts/build_data.py

Everything here is invented. The files are small enough to read, and the examples
and tests run the real pipeline and the real listing check over them.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chapter10.adapter import from_team_suite
from chapter10.gate import EvalResult
from chapter10.pipeline import run_pipeline

TEMPLATE = ROOT / "template-repository"
DATA = ROOT / "data"
RECORDS = DATA / "records"

GROUPS = {"wear": 10, "healthy": 8, "missing-data": 6, "parts": 6}
TASKS = [
    f"{group}-{n:02d}" for group, count in GROUPS.items() for n in range(1, count + 1)
]


def result(bundle: str, suite: str, failing: set[str], trials: int = 4) -> EvalResult:
    outcomes = {task: [True] * trials for task in TASKS}
    for task in failing:
        outcomes[task] = [True] * (trials - 1) + [False]
    tokens = len(TASKS) * trials * 5200
    return EvalResult(
        bundle=bundle,
        suite=suite,
        trials=trials,
        cached=False,
        outcomes=outcomes,
        tokens=tokens,
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=88))


def release_record(folder: Path, report: EvalResult, verdict: str = "pass") -> None:
    payload = json.dumps(report.model_dump(), indent=1) + "\n"
    write_text(folder / "eval-report.json", payload)
    record = {
        "bundle": report.bundle,
        "suite": report.suite,
        "verdict": verdict,
        "eval_report_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "produced_by": "release-pipeline",
    }
    write_json(folder / "release-record.json", record)


def build_evals() -> None:
    always = {"parts-06"}
    eager = {"healthy-02", "healthy-05", "healthy-07", "missing-data-01"}
    write_json(
        TEMPLATE / "evals" / "baseline.json",
        result(
            "maintenance-planner@41.2", "golden@41", always | {"missing-data-04"}
        ).model_dump(),
    )
    write_json(
        TEMPLATE / "evals" / "attempt-1.json",
        result(
            "maintenance-planner@41.3",
            "golden@41",
            always | {"missing-data-04"} | eager,
        ).model_dump(),
    )
    write_json(
        TEMPLATE / "evals" / "candidate.json",
        result("maintenance-planner@41.3", "golden@41", always).model_dump(),
    )
    fallback = always | {"wear-03", "wear-08", "missing-data-02"}
    write_json(
        TEMPLATE / "evals" / "fallback.json",
        result("maintenance-planner@41.3-fallback", "golden@41", fallback).model_dump(),
    )


def evidence(agent: str, results: str | None = None) -> dict[str, str]:
    folder = results or agent
    return {
        "tier_record": f"governance/tiers/{agent}.md",
        "eval_report": f"results/{folder}/eval-report.json",
        "release_record": f"results/{folder}/release-record.json",
        "security_review": f"reviews/{agent}.md",
        "oversight_note": f"governance/oversight/{agent}.md",
        "config_ref": f"bundles/{agent}.yaml",
    }


def signals(statuses: dict[str, str]) -> dict[str, dict[str, dict[str, str]]]:
    return {"signals": {name: {"status": status} for name, status in statuses.items()}}


def build_register() -> None:
    for folder in (RECORDS, DATA / "register", DATA / "candidates"):
        shutil.rmtree(folder, ignore_errors=True)

    # The maintenance planner: the real pipeline certifies the real candidate.
    planner = RECORDS / "results" / "maintenance-planner"
    run_pipeline(TEMPLATE, "block", out=planner)
    old = result("maintenance-planner@41.1", "golden@39", {"parts-06", "wear-04"})
    release_record(RECORDS / "results" / "maintenance-planner-41.1", old)

    # The joined service keeps its own suite. The adapter maps it to the gate.
    cases = [
        {
            "name": f"doc-{n:02d}",
            "attempts": [
                {
                    "status": "ok" if (n not in (7, 19, 23, 31) or t < 2) else "bad",
                    "tokens": 3100,
                }
                for t in range(3)
            ],
        }
        for n in range(1, 41)
    ]
    team_report = {"suite_name": "docqa", "suite_revision": 112, "cases": cases}
    write_json(DATA / "team-suite" / "document-assistant.json", team_report)
    joined = from_team_suite(team_report, bundle="document-assistant@7.0")
    release_record(RECORDS / "results" / "document-assistant", joined, verdict="warn")

    quote_outcomes = {f"quote-{n:02d}": [True] * 4 for n in range(1, 14)}
    quote_outcomes["quote-13"] = [True, True, False, True]
    quotes = EvalResult(
        bundle="parts-quote@0.9",
        suite="quotes@13",
        trials=4,
        cached=False,
        outcomes=quote_outcomes,
        tokens=13 * 4 * 2400,
    )
    release_record(RECORDS / "results" / "parts-quote", quotes)

    acceptance = EvalResult(
        bundle="purchasing-advisor@2026.11",
        suite="acceptance@3",
        trials=1,
        cached=False,
        outcomes={f"accept-{n:02d}": [True] for n in range(1, 13)},
        tokens=0,
    )
    release_record(RECORDS / "results" / "purchasing-advisor", acceptance)

    agents = {
        "maintenance-planner": (
            "high",
            "Drafts work orders. A planner approves each one.",
        ),
        "document-assistant": (
            "medium",
            "Answers questions from engineering procedures.",
        ),
        "parts-quote": (
            "medium",
            "Drafts customer quotes. A sales engineer sends them.",
        ),
        "purchasing-advisor": (
            "medium",
            "Suggests suppliers to buyers. Buyers decide.",
        ),
    }
    for agent, (tier, purpose) in agents.items():
        write_text(
            RECORDS / "governance" / "tiers" / f"{agent}.md",
            f"Tier: {tier}. {purpose}\n",
        )
        write_text(
            RECORDS / "reviews" / f"{agent}.md",
            f"Security review of {agent}: passed.\n",
        )
        write_text(RECORDS / "bundles" / f"{agent}.yaml", f"bundle: {agent}\n")
    shutil.copy(
        TEMPLATE / "bundle.yaml", RECORDS / "bundles" / "maintenance-planner.yaml"
    )
    oversight = (
        "Every work order waits for a named plant planner. See the approval queue.\n"
    )
    write_text(
        RECORDS / "governance" / "oversight" / "maintenance-planner.md", oversight
    )

    monitoring = {
        "maintenance-planner": dict.fromkeys(
            ["model", "input", "knowledge", "outcome", "cost"], "ok"
        ),
        "document-assistant": {
            "model": "ok",
            "input": "not_configured",
            "knowledge": "ok",
            "outcome": "ok",
            "cost": "ok",
        },
        "parts-quote": {
            "model": "ok",
            "input": "ok",
            "knowledge": "not_configured",
            "outcome": "ok",
            "cost": "ok",
        },
        "purchasing-advisor": {
            "model": "not_observable",
            "input": "not_configured",
            "knowledge": "not_observable",
            "outcome": "not_configured",
            "cost": "ok",
        },
    }
    for agent, statuses in monitoring.items():
        write_json(RECORDS / "monitoring" / f"{agent}.json", signals(statuses))

    def entry(agent: str, **fields: object) -> dict[str, object]:
        base = {
            "agent": agent,
            "owner": fields.pop("owner"),
            "route": fields.pop("route"),
            "tier": agents[agent][0],
            "status": fields.pop("status"),
            "bundle": fields.pop("bundle"),
            "budget": fields.pop("budget"),
            "evidence": fields.pop("evidence", evidence(agent)),
            "data_sources": fields.pop("data_sources"),
            "value_line": fields.pop("value_line"),
            "monitoring": f"monitoring/{agent}.json",
        }
        return base

    planner_entry = entry(
        "maintenance-planner",
        owner="platform-team",
        route="build",
        status="steady",
        bundle="maintenance-planner@41.3",
        budget={"monthly_usd": 2500, "source": "metered", "last_month_usd": 2120},
        data_sources=["sensor-history", "repair-history"],
        value_line={
            "claim": "work orders approved 1.5 days earlier",
            "stage": "measured",
        },
    )
    write_yaml(DATA / "register" / "01-maintenance-planner.yaml", planner_entry)

    no_oversight = evidence("maintenance-planner", "maintenance-planner-41.1")
    no_oversight.pop("oversight_note")
    first = dict(planner_entry, status="live", evidence=no_oversight)
    write_yaml(DATA / "candidates" / "attempt-1.yaml", first)
    second = dict(
        first, evidence=evidence("maintenance-planner", "maintenance-planner-41.1")
    )
    write_yaml(DATA / "candidates" / "attempt-2.yaml", second)
    third = dict(first, evidence=evidence("maintenance-planner"))
    write_yaml(DATA / "candidates" / "attempt-3.yaml", third)

    doc_evidence = evidence("document-assistant")
    doc_evidence.pop("oversight_note")
    write_yaml(
        DATA / "register" / "02-document-assistant.yaml",
        entry(
            "document-assistant",
            owner="engineering-systems",
            route="join",
            status="listed",
            bundle="document-assistant@7.0",
            budget={"monthly_usd": 1500, "source": "metered", "last_month_usd": 1135},
            evidence=doc_evidence,
            data_sources=["engineering-procedures"],
            value_line={
                "claim": "procedure found in 2 minutes, not 15",
                "stage": "baselined",
            },
        ),
    )
    quote_evidence = evidence("parts-quote")
    quote_evidence.pop("oversight_note")
    write_yaml(
        DATA / "register" / "03-parts-quote.yaml",
        entry(
            "parts-quote",
            owner="sales-engineering",
            route="assemble",
            status="live",
            bundle="parts-quote@0.9",
            budget={"monthly_usd": 100, "source": "metered", "last_month_usd": 53},
            evidence=quote_evidence,
            data_sources=["price-list"],
            value_line={"claim": "quotes sent the same day", "stage": "measured"},
        ),
    )
    buy_evidence = evidence("purchasing-advisor")
    buy_evidence.pop("oversight_note")
    buy_evidence["config_ref"] = "gap-sheets/purchasing-advisor.yaml"
    write_yaml(
        DATA / "register" / "04-purchasing-advisor.yaml",
        entry(
            "purchasing-advisor",
            owner="procurement",
            route="buy",
            status="contracted",
            bundle="purchasing-advisor@2026.11",
            budget={"monthly_usd": 1200, "source": "allocated", "last_month_usd": 1050},
            evidence=buy_evidence,
            data_sources=["supplier-master"],
            value_line={
                "claim": "buyer review time down 20 percent",
                "stage": "declared",
            },
        ),
    )

    gap = {
        "agent": "purchasing-advisor",
        "tier": "medium",
        "requirements": {
            "identification": {"status": "met", "note": "acts as the signed-in buyer"},
            "security_review": {
                "status": "met",
                "note": "covered by the vendor review",
            },
            "action_limits": {
                "status": "met",
                "note": "suggests only; buyers place orders",
            },
            "audit_records": {
                "status": "compensating_control",
                "note": "no span-level trace; weekly export of activity records",
            },
            "lifecycle_notice": {
                "status": "contract",
                "note": "30 days of notice before a model change, added at renewal",
            },
            "usage_evidence": {
                "status": "risk_acceptance",
                "note": "no per-agent metering; cost allocated by seat",
                "accepted_by": "head of procurement",
            },
        },
    }
    write_yaml(RECORDS / "gap-sheets" / "purchasing-advisor.yaml", gap)


def build_catalogs() -> None:
    write_yaml(
        DATA / "requirements.yaml",
        {
            "low": ["tier_record", "eval_report", "release_record", "config_ref"],
            "medium": [
                "tier_record",
                "eval_report",
                "release_record",
                "security_review",
                "config_ref",
            ],
            "high": [
                "tier_record",
                "eval_report",
                "release_record",
                "security_review",
                "oversight_note",
                "config_ref",
            ],
        },
    )
    write_yaml(
        DATA / "inventory.yaml",
        {
            "gateway_keys": [
                {"name": "maintenance-planner-prod", "agent": "maintenance-planner"},
                {"name": "docs-assistant-prod", "agent": "document-assistant"},
            ],
            "identities": [
                {"name": "agent-maintenance-planner", "agent": "maintenance-planner"}
            ],
            "provider_invoices": [
                {
                    "name": "direct API account, sales engineering",
                    "agent": "parts-quote",
                }
            ],
            "vendor_features": [
                {
                    "name": "purchasing suite: AI suggestions",
                    "agent": "purchasing-advisor",
                }
            ],
        },
    )
    write_yaml(
        DATA / "marketplace.yaml",
        [
            {
                "agent": "maintenance-planner",
                "capabilities": [
                    "sensor-history",
                    "maintenance-history",
                    "work-orders",
                    "approval-queue",
                    "summarize",
                ],
            },
            {
                "agent": "document-assistant",
                "capabilities": [
                    "engineering-procedures",
                    "search",
                    "summarize",
                    "cite",
                ],
            },
        ],
    )
    write_yaml(
        DATA / "vendors.yaml",
        [
            {
                "product": "finance suite assistant",
                "capabilities": ["expense-coding", "receipts", "ledger", "approvals"],
            },
            {
                "product": "purchasing suite suggestions",
                "capabilities": ["supplier-search", "purchase-orders", "price-compare"],
            },
        ],
    )
    write_yaml(
        DATA / "briefs.yaml",
        [
            {
                "name": "shift-handover",
                "purpose": "summarize open work orders for the next shift",
                "audience": "shift supervisors",
                "reviewer": "shift supervisor",
                "data_tier": "medium",
                "capabilities": ["summarize", "maintenance-history", "work-orders"],
                "company_specific": False,
            },
            {
                "name": "expense-coding",
                "purpose": "code expense receipts to the ledger",
                "audience": "finance clerks",
                "reviewer": "finance clerk",
                "data_tier": "medium",
                "capabilities": ["expense-coding", "receipts", "ledger"],
                "company_specific": False,
            },
            {
                "name": "parts-quote",
                "purpose": "draft a customer quote from the price list",
                "audience": "sales engineers",
                "reviewer": "sales engineer",
                "data_tier": "medium",
                "capabilities": ["price-list", "quote-draft", "discount-rules"],
                "company_specific": True,
            },
        ],
    )


if __name__ == "__main__":
    build_evals()
    build_catalogs()
    build_register()
    print("data written")
