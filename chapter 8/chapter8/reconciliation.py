"""Quarantined reading and deterministic reconciliation writes."""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MedicationChange, PatientFixture, ReconciliationProposal

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "data" / "fixtures"
FIXTURES = {
    "clean": FIXTURE_DIR / "patient_clean.json",
    "hostile_note": FIXTURE_DIR / "patient_hostile_note.json",
    "other_patient": FIXTURE_DIR / "patient_other.json",
}

INJECTION_SIGNALS = {
    "instruction_override": re.compile(
        r"(?i)\b(ignore|disregard|override)\b.{0,40}\b(instruction|policy|previous)\b"
    ),
    "secret_request": re.compile(
        r"(?i)\b(reveal|send|export|upload)\b.{0,40}\b(secret|token|credential|record)\b"
    ),
    "tool_direction": re.compile(
        r"(?i)\b(call|invoke|run|execute)\b.{0,30}\b(tool|writer|request)\b"
    ),
}


def load_fixture(name: str) -> PatientFixture:
    try:
        path = FIXTURES[name]
    except KeyError as exc:
        raise ValueError(f"unknown fixture: {name}") from exc
    return PatientFixture.model_validate_json(path.read_text(encoding="utf-8"))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SyntheticRecordStore:
    def __init__(self, patients: list[PatientFixture]) -> None:
        self._patients = {patient.patient_id: patient.model_copy(deep=True) for patient in patients}
        self._writes: list[dict[str, Any]] = []

    @property
    def writes(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._writes))

    @property
    def patient_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._patients))

    def patient(self, patient_id: str) -> PatientFixture:
        try:
            return self._patients[patient_id].model_copy(deep=True)
        except KeyError as exc:
            raise LookupError(f"unknown patient: {patient_id}") from exc

    def medications(self, patient_id: str) -> list[dict[str, Any]]:
        return [
            medication.model_dump(mode="json")
            for medication in self.patient(patient_id).medications
        ]

    def fills(self, patient_id: str) -> list[dict[str, Any]]:
        return [fill.model_dump(mode="json") for fill in self.patient(patient_id).recent_fills]

    def apply(self, proposal: ReconciliationProposal, *, clinician_ref: str) -> str:
        record_ref = f"MedicationRequest/reconciliation-{len(self._writes) + 1:04d}"
        self._writes.append(
            {
                "record_ref": record_ref,
                "patient_id": proposal.patient_id,
                "proposal_id": proposal.proposal_id,
                "clinician_ref": clinician_ref,
                "changes": [change.model_dump(mode="json") for change in proposal.changes],
            }
        )
        return record_ref


class QuarantinedReader:
    def __init__(self, store: SyntheticRecordStore) -> None:
        self.store = store

    def build_proposal(self, patient_id: str, *, now: datetime) -> ReconciliationProposal:
        patient = self.store.patient(patient_id)
        note_hashes = {note.note_id: content_hash(note.text) for note in patient.notes}
        detector_flags = sorted(
            {
                f"{note.note_id}:{label}"
                for note in patient.notes
                for label, pattern in INJECTION_SIGNALS.items()
                if pattern.search(note.text)
            }
        )
        active = {
            medication.code: medication
            for medication in patient.medications
            if medication.status == "active"
        }
        fills = {fill.medication_code: fill for fill in patient.recent_fills}
        changes: list[MedicationChange] = []
        for code, fill in sorted(fills.items()):
            if code not in active:
                changes.append(
                    MedicationChange(
                        operation="review",
                        medication_code=code,
                        medication_name=fill.medication_name,
                        reason_code="fill_without_active_order",
                        evidence_refs=[f"MedicationDispense/{code}"],
                    )
                )
        for code, medication in sorted(active.items()):
            if code not in fills:
                changes.append(
                    MedicationChange(
                        operation="review",
                        medication_code=code,
                        medication_name=medication.name,
                        reason_code="active_order_without_recent_fill",
                        evidence_refs=[f"MedicationRequest/{code}"],
                    )
                )
        observed_codes = set(active) | set(fills)
        if {"RXNORM-1191", "RXNORM-11289"}.issubset(observed_codes):
            changes.append(
                MedicationChange(
                    operation="review",
                    medication_code="RXNORM-1191+RXNORM-11289",
                    medication_name="aspirin and warfarin",
                    reason_code="interaction_review_required",
                    evidence_refs=["InteractionKnowledgeBase/warfarin-aspirin"],
                )
            )
        seed = f"{patient_id}:{now.isoformat()}:{sorted(note_hashes.values())}"
        proposal_id = f"proposal-{content_hash(seed)[:16]}"
        return ReconciliationProposal(
            proposal_id=proposal_id,
            patient_id=patient_id,
            changes=changes,
            source_hashes=note_hashes,
            detector_flags=detector_flags,
            created_at=now,
        )
