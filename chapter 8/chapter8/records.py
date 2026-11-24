"""A stand-in for the hospital's record server. Every record in it is synthetic.

The store checks the token on every call and writes its own audit events. It does
not trust the agent, the guardrail, or anything else in front of it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from chapter8.session import Session, Tokens
from chapter8.settings import DATA

INTERACTIONS = {
    frozenset({"warfarin", "aspirin"}): "bleeding risk",
    frozenset({"lisinopril", "spironolactone"}): "high potassium risk",
}


class Forbidden(Exception):
    """The record server refused the token."""


class Medication(BaseModel):
    id: str
    name: str
    dose: str
    status: str = "active"


class Fill(BaseModel):
    id: str
    name: str
    dose: str
    filled_on: str
    days_supply: int


class Allergy(BaseModel):
    id: str
    substance: str


class Note(BaseModel):
    id: str
    author: str
    written_on: str
    text: str
    labels: list[str] = Field(default_factory=list)


class Patient(BaseModel):
    id: str
    name: str
    date_of_birth: str
    mrn: str
    phone: str
    version: int
    medications: list[Medication]
    fills: list[Fill]
    allergies: list[Allergy]
    notes: list[Note]
    flags: list[str] = Field(default_factory=list)


def load_patient(name: str) -> Patient:
    path = DATA / "fixtures" / f"{name}.json"
    return Patient.model_validate(json.loads(path.read_text()))


RESOURCES = {
    "MedicationRequest": "medications",
    "MedicationDispense": "fills",
    "AllergyIntolerance": "allergies",
    "DocumentReference": "notes",
}


class RecordStore:
    def __init__(
        self,
        patients: list[Patient],
        tokens: Tokens,
        clock: Callable[[], datetime],
    ) -> None:
        self._patients = {patient.id: patient for patient in patients}
        self.tokens = tokens
        self.clock = clock
        self.audit: list[dict[str, Any]] = []

    def _authorize(self, session: Session, scope: str) -> Patient:
        if not self.tokens.valid(session):
            raise Forbidden("token is expired or revoked")
        if scope not in session.scopes:
            raise Forbidden(f"token lacks {scope}")
        return self._patients[session.patient_id]

    def read(self, session: Session, resource: str) -> list[dict[str, Any]]:
        patient = self._authorize(session, f"patient/{resource}.rs")
        rows = []
        for item in getattr(patient, RESOURCES[resource]):
            row = item.model_dump()
            if "restricted" in row.get("labels", []):
                row = {
                    "id": row["id"],
                    "withheld": "restricted label, no consent",
                }
            rows.append(row)
            session.seen.add(row["id"])
            self._record(session, "R", row["id"], "0")
        return rows

    def version(self, patient_id: str) -> int:
        return self._patients[patient_id].version

    def medication(
        self, patient_id: str, record_id: str
    ) -> Medication | Fill | None:
        patient = self._patients[patient_id]
        for item in [*patient.medications, *patient.fills]:
            if item.id == record_id:
                return item
        return None

    def update(self, session: Session, changes: list[dict[str, Any]]) -> str:
        patient = self._authorize(session, "patient/MedicationRequest.u")
        for change in changes:
            self._apply(patient, change)
        patient.version += 1
        reference = f"Patient/{patient.id}/_history/{patient.version}"
        self._record(session, "U", reference, "0")
        return reference

    def _apply(self, patient: Patient, change: dict[str, Any]) -> None:
        target = change["target"]
        if change["action"] == "discontinue":
            for medication in patient.medications:
                if medication.id == target:
                    medication.status = "stopped"
        elif change["action"] == "add":
            fill = next(fill for fill in patient.fills if fill.id == target)
            number = len(patient.medications) + 101
            patient.medications.append(
                Medication(
                    id=f"MedicationRequest/mr-{number}",
                    name=fill.name,
                    dose=fill.dose,
                )
            )
        else:
            patient.flags.append(f"{target}: {change['reason']}")

    def _record(
        self, session: Session, action: str, what: str, outcome: str
    ) -> None:
        from chapter8.audit import audit_event

        self.audit.append(
            audit_event(session, action, what, outcome, self.clock())
        )


def check_interactions(names: list[str]) -> list[dict[str, str]]:
    """Known interactions among a list of medication names."""
    wanted = {name.lower().split()[0] for name in names}
    found = []
    for pair, risk in INTERACTIONS.items():
        if pair <= wanted:
            identifier = "Interaction/" + "+".join(sorted(pair))
            found.append({"id": identifier, "risk": risk})
    return found
