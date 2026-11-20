"""The alert triage pyramid: a small model sorts, code decides, people own the rest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel

from chapter5.investigation import InvestigationResult
from chapter5.models import MODELS, QUICK
from chapter5.run_control import RetryLedger, run_investigation

TRIAGE_GUIDE = """You triage one anti-money-laundering alert.
Decide whether the alerted activity can be explained by the records you are
given. Recommend "clear" only when the records show an established, ordinary
pattern. Otherwise recommend "investigate". Name the laundering typologies you
considered. In evidence, list only identifiers from the RECORDS section, one
per item, written exactly as shown, such as txn-1234. Do not list the alert
itself and do not add any other text. Report your confidence between 0 and 1."""

Route = Literal[
    "auto_cleared",
    "human_confirm_clear",
    "investigation",
    "human_review",
    "analyst_review",
]


class Alert(BaseModel):
    alert_id: str
    alert_type: str
    customer_id: str
    case_text: str
    records: dict[str, str]


class TriageVerdict(BaseModel):
    recommendation: Literal["clear", "investigate"]
    confidence: float
    matched_typologies: list[str]
    evidence: list[str]
    rationale: str


alert_triage = Agent(
    name="alert_triage",
    model=MODELS.small,
    model_settings=QUICK,
    instructions=TRIAGE_GUIDE,
    output_type=TriageVerdict,
)


class Disposition(BaseModel):
    alert_id: str
    route: Route


@dataclass(frozen=True)
class AlertPolicy:
    may_auto_clear: bool
    clear_above: float


NEVER_AUTO_CLEAR = AlertPolicy(may_auto_clear=False, clear_above=1.0)
DISPOSITION_POLICY = {
    "large_transfer": AlertPolicy(may_auto_clear=True, clear_above=0.90),
    "structuring": NEVER_AUTO_CLEAR,
    "sanctions_proximity": NEVER_AUTO_CLEAR,
}
SAMPLE_SHARE = 0.02


def load_alerts() -> list[Alert]:
    path = Path(__file__).parent.parent / "data" / "cases.json"
    return [Alert(**item) for item in json.loads(path.read_text())["alerts"]]


def case_file(alert: Alert) -> str:
    records = "\n".join(f"{ref}: {text}" for ref, text in alert.records.items())
    return (
        f"Alert {alert.alert_id} ({alert.alert_type}) on customer {alert.customer_id}\n"
        f"{alert.case_text}\n\nRECORDS (identifier: content)\n{records}"
    )


def cites_real_records(verdict: TriageVerdict, alert: Alert) -> bool:
    return bool(verdict.evidence) and all(
        ref in alert.records for ref in verdict.evidence
    )


def in_quality_sample(alert_id: str, share: float = SAMPLE_SHARE) -> bool:
    digest = hashlib.sha256(alert_id.encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32 < share


@dataclass
class Desk:
    """Where dispositions are recorded and where people pick up their work."""

    log: list[tuple[str, Route, TriageVerdict | None]] = field(default_factory=list)
    people: list[tuple[str, Route]] = field(default_factory=list)
    quality_sample: list[str] = field(default_factory=list)

    def send(
        self, alert: Alert, verdict: TriageVerdict | None, route: Route
    ) -> Disposition:
        self.log.append((alert.alert_id, route, verdict))
        if route in ("human_confirm_clear", "human_review", "analyst_review"):
            self.people.append((alert.alert_id, route))
        if route == "auto_cleared" and in_quality_sample(alert.alert_id):
            self.quality_sample.append(alert.alert_id)
        return Disposition(alert_id=alert.alert_id, route=route)


async def dispose_alert(alert: Alert, desk: Desk) -> Disposition:
    run = await Runner.run(alert_triage, case_file(alert), max_turns=1)
    verdict = run.final_output
    policy = DISPOSITION_POLICY.get(alert.alert_type, NEVER_AUTO_CLEAR)
    if not cites_real_records(verdict, alert):
        return desk.send(alert, verdict, route="human_review")
    if verdict.recommendation == "investigate":
        return desk.send(alert, verdict, route="investigation")
    if policy.may_auto_clear and verdict.confidence >= policy.clear_above:
        return desk.send(alert, verdict, route="auto_cleared")
    return desk.send(alert, verdict, route="human_confirm_clear")


async def process_alert(
    alert: Alert, desk: Desk, retries: RetryLedger
) -> tuple[Disposition, InvestigationResult | None]:
    """Layer 1, then Layer 2 when needed. Layer 3 is the people the desk hands to."""
    disposition = await dispose_alert(alert, desk)
    if disposition.route != "investigation":
        return disposition, None
    result = await run_investigation(alert.alert_id, case_file(alert), retries)
    return desk.send(alert, None, route="analyst_review"), result
