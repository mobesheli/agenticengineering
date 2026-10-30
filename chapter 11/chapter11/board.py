"""Replay the local register's year through the same controls used in the notebook."""

from __future__ import annotations

import json
from pathlib import Path

from .artifacts import load_json
from .autonomy import load_rules, promote, promotion_digest, should_drop
from .drift import configuration_changes, decide
from .models import (
    AgentEntry,
    Approval,
    Event,
    PromotionEvidence,
    Reading,
    RunConfiguration,
)


def load_register() -> list[AgentEntry]:
    return [AgentEntry.model_validate(entry) for entry in load_json("register.json")]


def replay(day: int = 365, *, events: list[Event] | None = None) -> dict:
    if not 0 <= day <= 365:
        raise ValueError("day must be between 0 and 365")
    events = (
        events
        if events is not None
        else [Event.model_validate(e) for e in load_json("events.json")]
    )
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("event IDs must be unique")
    entry = load_register()[0].model_copy(update={"attested_day": 0})
    pinned = RunConfiguration.model_validate(load_json("configuration.json"))
    effective = pinned.model_copy(deep=True)
    rules = load_rules()
    history = []
    for event in sorted(events, key=lambda e: e.day):
        if event.day > day:
            break
        payload = event.payload
        decision, detail = "recorded", payload.get("detail", "")
        if event.kind == "drift":
            effective = RunConfiguration.model_validate(payload["effective"])
            readings = [Reading.model_validate(r) for r in payload["readings"]]
            changed = configuration_changes(pinned, effective)
            decision = decide(readings, not changed).value
            entry.drift_hold_active = decision == "hold"
            detail = (
                "configuration changes: " + ", ".join(changed) if changed else decision
            )
            entry.drift = {
                r.signal: "outside band" if r.moved else "within band" for r in readings
            }
            if changed:
                entry.drift["model"] = "configuration hold"
        elif event.kind == "release":
            # Release events are already approved records, not an automatic release path.
            entry.bundle = payload["bundle"]
            entry.drift_hold_active = False
            entry.cost_per_outcome = payload["cost"]
            pinned = RunConfiguration.model_validate(payload["configuration"])
            effective = pinned.model_copy(deep=True)
            entry.drift = {key: "within band" for key in entry.drift}
            decision = "released"
        elif event.kind == "drop":
            if should_drop(payload, rules[2]):
                entry.rung = 0
                decision = "demoted"
        elif event.kind == "promotion":
            evidence = PromotionEvidence.model_validate(payload["evidence"])
            rule = rules[payload["target"]]
            subject = promotion_digest(entry, evidence, rule.target)
            approvals = [
                Approval(role=role, name=name, subject_digest=subject)
                for role, name in payload["signers"].items()
            ]
            try:
                entry = promote(entry, evidence, rule, approvals, day=event.day)
                decision = "promoted"
            except ValueError as exc:
                decision, detail = "refused", str(exc)
        elif event.kind == "attest":
            entry.sponsor = payload["sponsor"]
            entry.attested_day = event.day
            decision = "attested"
        elif event.kind == "sponsor_left":
            entry.sponsor = None
            decision = "unsponsored"
        if "cost" in payload:
            entry.cost_per_outcome = payload["cost"]
        history.append(
            {
                "day": event.day,
                "event_id": event.event_id,
                "title": event.title,
                "decision": decision,
                "detail": detail,
                "rung": entry.rung,
            }
        )
    return {
        "day": day,
        "entry": entry.model_dump(),
        "sponsored": entry.sponsored(day),
        "renewal": "eligible for review"
        if entry.sponsored(day)
        else "blocked: sponsor attestation required",
        "effective_configuration": effective.model_dump(),
        "pinned_configuration": pinned.model_dump(),
        "events": history,
    }


def replay_year() -> list[dict]:
    events = [Event.model_validate(e) for e in load_json("events.json")]
    return [replay(day, events=events) for day in range(366)]


def write_board(path: Path, frames: list[dict] | None = None) -> None:
    frames = replay_year() if frames is None else frames
    template = (
        Path(__file__).with_name("board_template.html").read_text(encoding="utf-8")
    )
    data = json.dumps(frames, separators=(",", ":")).replace("<", "\\u003c")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template.replace("__FRAMES__", data), encoding="utf-8")
