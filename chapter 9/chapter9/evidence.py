"""Export one review-ready ledger, two views, and a hashed manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .dashboard import (
    build_engineering_dashboard,
    build_finance_dashboard,
    render_finance_dashboard,
)
from .models import TraceRecord
from .routing import token_share_by_step


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def emit_value_evidence(
    traces: list[TraceRecord],
    output_dir: Path,
    *,
    quarter_budget_usd: float = 250.0,
    invoice_usd: float | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    finance = build_finance_dashboard(
        traces,
        quarter_budget_usd=quarter_budget_usd,
        invoice_usd=invoice_usd,
    )
    engineering = build_engineering_dashboard(traces)
    artifacts = {
        "finance_dashboard.json": _json(finance),
        "engineering_dashboard.json": _json(engineering),
        "token_share_by_step.json": _json(token_share_by_step(traces)),
        "priced_traces.jsonl": "".join(
            json.dumps(trace.model_dump(mode="json"), sort_keys=True) + "\n"
            for trace in traces
        ),
        "value_review.html": render_finance_dashboard(finance),
    }
    records = []
    for name, content in artifacts.items():
        records.append({"path": name, "sha256": _write(output_dir / name, content)})
    manifest = {
        "trace_count": len(traces),
        "price_card_versions": sorted(
            {
                str(span.attributes["price_card_version"])
                for trace in traces
                for span in trace.spans
                if "price_card_version" in span.attributes
            }
        ),
        "records": records,
    }
    manifest_path = output_dir / "manifest.json"
    _write(manifest_path, _json(manifest))
    return manifest_path


def verify_manifest(manifest_path: Path) -> bool:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return all(
        hashlib.sha256((manifest_path.parent / row["path"]).read_bytes()).hexdigest()
        == row["sha256"]
        for row in manifest["records"]
    )
