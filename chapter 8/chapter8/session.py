"""Who the agent is acting for, on which patient, with which scopes, until when.

`Tokens` stands in for the hospital's authorization server and the SMART on FHIR
launch. The session comes from the launch. Nothing in it comes from the model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class PhaseScopes:
    read_phase: frozenset[str]
    write_phase: frozenset[str]


RECONCILIATION = PhaseScopes(
    read_phase=frozenset(
        {
            "patient/MedicationRequest.rs",
            "patient/MedicationDispense.rs",
            "patient/AllergyIntolerance.rs",
            "patient/DocumentReference.rs",
        }
    ),
    write_phase=frozenset({"patient/MedicationRequest.u"}),
)
AGENTS = {"read": "reconciliation-reader", "write": "reconciliation-writer"}


def scopes_for(phase: str) -> frozenset[str]:
    if phase == "read":
        return RECONCILIATION.read_phase
    if phase == "write":
        return RECONCILIATION.write_phase
    raise ValueError(f"unknown phase: {phase}")


@dataclass
class Session:
    token_id: str
    agent_id: str
    clinician: str
    role: str
    patient_id: str
    scopes: frozenset[str]
    expires_at: datetime
    seen: set[str] = field(default_factory=set)


class Tokens:
    """Issues short-lived sessions and revokes them."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self.clock = clock
        self._issued: list[Session] = []
        self._revoked: set[str] = set()

    def launch(
        self, phase: str, clinician: str, patient_id: str, minutes: int = 5
    ) -> Session:
        session = Session(
            token_id=f"tok-{len(self._issued) + 1:04d}",
            agent_id=AGENTS[phase],
            clinician=clinician,
            role="clinician",
            patient_id=patient_id,
            scopes=scopes_for(phase),
            expires_at=self.clock() + timedelta(minutes=minutes),
        )
        self._issued.append(session)
        return session

    def valid(self, session: Session) -> bool:
        if session.token_id in self._revoked:
            return False
        return self.clock() < session.expires_at

    def revoke_agent(self, agent_id: str) -> int:
        live = [
            s for s in self._issued if s.agent_id == agent_id and self.valid(s)
        ]
        self._revoked.update(session.token_id for session in live)
        return len(live)
