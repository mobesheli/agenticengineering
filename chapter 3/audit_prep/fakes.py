"""Small in-memory stand-ins for the three systems behind the MCP servers.

The data is synthetic and tiny. The contracts are the point: reads are
parameterized and bounded, the evidence store deduplicates artifact writes on
their content hash, and publication verifies the bundle hash it was approved
against before it crosses into irreversible state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def stable_hash(payload: Any) -> str:
    """Return a short sha256 of a JSON value with sorted keys."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


@dataclass
class FakeFinanceData:
    """Trial balances and journal entries for one entity."""

    balances: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            "2026-Q3": {
                "1000 Cash and cash equivalents": 5_104_300,
                "1200 Trade receivables": 1_488_900,
                "2000 Trade payables": -1_020_750,
                "2400 Short-term borrowings": -2_500_000,
                "4000 Revenue": -7_915_000,
                "6000 Operating expenses": 4_842_550,
            }
        }
    )
    journal: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"je": "JE-20931", "account": "2400", "amount": 2_500_000, "memo": "Revolver drawdown"},
            {"je": "JE-20977", "account": "1200", "amount": 612_400, "memo": "Q3 invoicing batch"},
            {"je": "JE-21002", "account": "6000", "amount": 388_150, "memo": "Cloud hosting"},
            {"je": "JE-21040", "account": "1000", "amount": 1_250_000, "memo": "Customer receipt"},
            {"je": "JE-21077", "account": "2000", "amount": 94_200, "memo": "Vendor settlement"},
        ]
    )
    bundles_on_record: set[str] = field(default_factory=set)

    def snapshot(self, *, period: str, entity: str, materiality_threshold: int) -> dict:
        rows = self.balances.get(period, {})
        lines = [
            {"account": account, "balance": balance}
            for account, balance in rows.items()
            if abs(balance) >= materiality_threshold
        ]
        return {"ok": True, "entity": entity, "period": period,
                "source_ref": f"tb:{entity}:{period}", "lines": lines}

    def journal_entries(self, *, period: str, above_amount: int, cursor: int, page_size: int) -> dict:
        matching = [e for e in self.journal if e["amount"] >= above_amount]
        page = matching[cursor:cursor + page_size]
        next_cursor = cursor + page_size if cursor + page_size < len(matching) else None
        return {"ok": True, "period": period, "entries": page,
                "source_refs": [f"je:{e['je']}" for e in page], "next_cursor": next_cursor}


@dataclass
class FakePolicy:
    """Regulatory reporting requirements, pinned by effective date."""

    version: str = "rules-2026.07"
    required_artifacts: dict[str, list[str]] = field(
        default_factory=lambda: {
            "uk": ["trial_balance", "journal_sample", "requirements_extract"],
            "us": ["trial_balance", "journal_sample", "requirements_extract", "management_attestation"],
            "eu": ["trial_balance", "journal_sample", "requirements_extract"],
        }
    )

    def requirements(self, *, jurisdiction: str, report_type: str, effective_date: str) -> dict:
        kinds = self.required_artifacts.get(jurisdiction)
        if kinds is None:
            return {"ok": False, "error_class": "not_found", "retryable": False,
                    "user_safe_message": "No reporting rules are held for that jurisdiction.",
                    "machine_action_hint": "ask_user"}
        return {"ok": True, "jurisdiction": jurisdiction, "report_type": report_type,
                "effective_date": effective_date, "policy_version": self.version,
                "required_artifacts": kinds, "materiality_threshold": 1_000_000}


@dataclass
class FakeEvidenceStore:
    """Draft bundles, hash-deduplicated artifacts, and a gated publish."""

    bundles: dict[str, dict[str, Any]] = field(default_factory=dict)
    published: list[str] = field(default_factory=list)

    def preview_bundle(self, *, control_id: str, period: str) -> dict:
        bundle_id = f"eb_{stable_hash([control_id, period])[:8]}"
        self.bundles.setdefault(bundle_id, {"control_id": control_id, "period": period,
                                            "artifacts": {}})
        return {"ok": True, "bundle_id": bundle_id, "status": "draft",
                "planned_sections": ["trial_balance", "journal_sample", "requirements_extract"]}

    def write_artifact(self, *, bundle_id: str, kind: str, content: str) -> dict:
        bundle = self.bundles.get(bundle_id)
        if bundle is None:
            return {"ok": False, "error_class": "not_found", "retryable": False,
                    "user_safe_message": "That bundle does not exist. Create it first.",
                    "machine_action_hint": "replan"}
        content_hash = stable_hash(content)
        existing = bundle["artifacts"].get(kind)
        replayed = existing is not None and existing["content_hash"] == content_hash
        if not replayed:
            bundle["artifacts"][kind] = {"content_hash": content_hash, "content": content}
        return {"ok": True, "bundle_id": bundle_id, "kind": kind,
                "content_hash": content_hash, "replayed": replayed,
                "bundle_hash": self.bundle_hash(bundle_id)}

    def bundle_hash(self, bundle_id: str) -> str | None:
        bundle = self.bundles.get(bundle_id)
        if bundle is None:
            return None
        return stable_hash({k: v["content_hash"] for k, v in bundle["artifacts"].items()})

    def publish(self, *, bundle_id: str, content_hash: str) -> dict:
        expected = self.bundle_hash(bundle_id)
        if expected is None:
            return {"ok": False, "error_class": "not_found", "retryable": False,
                    "user_safe_message": "That bundle does not exist.",
                    "machine_action_hint": "replan"}
        if content_hash != expected:
            return {"ok": False, "error_class": "content_hash_mismatch", "retryable": False,
                    "user_safe_message": "The bundle changed after it was approved.",
                    "developer_detail": f"approved {content_hash}, current {expected}",
                    "machine_action_hint": "replan"}
        if bundle_id in self.published:
            return {"ok": True, "bundle_id": bundle_id, "status": "published", "replayed": True}
        self.published.append(bundle_id)
        return {"ok": True, "bundle_id": bundle_id, "status": "published", "replayed": False}

    def artifact_kinds(self, bundle_id: str) -> list[str]:
        bundle = self.bundles.get(bundle_id)
        return sorted(bundle["artifacts"]) if bundle else []
