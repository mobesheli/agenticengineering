"""Threat-modeling helpers from the Chapter 8 design method."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IncidentClass(str, Enum):
    INJECTION = "injection"
    EXCESSIVE_PRIVILEGE = "excessive_privilege"
    SUPPLY_CHAIN = "supply_chain"
    MISSING_GATE = "missing_gate"


@dataclass(frozen=True)
class CapabilityProfile:
    processes_untrusted_input: bool
    reaches_sensitive_systems: bool
    changes_state_or_communicates: bool

    @property
    def capability_count(self) -> int:
        return sum(
            (
                self.processes_untrusted_input,
                self.reaches_sensitive_systems,
                self.changes_state_or_communicates,
            )
        )

    @property
    def requires_gate(self) -> bool:
        return self.capability_count == 3


class RiskTier(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE_WRITE = "reversible_write"
    EXTERNAL_COMMUNICATION = "external_communication"
    IRREVERSIBLE_WRITE = "irreversible_write"


def autonomy_route(risk_tier: RiskTier) -> str:
    routes = {
        RiskTier.READ_ONLY: "autonomous_with_monitoring",
        RiskTier.REVERSIBLE_WRITE: "execute_with_audit",
        RiskTier.EXTERNAL_COMMUNICATION: "stage_for_approval",
        RiskTier.IRREVERSIBLE_WRITE: "require_action_bound_approval",
    }
    return routes[risk_tier]


RECONCILIATION_READ = CapabilityProfile(True, True, False)
RECONCILIATION_WRITE = CapabilityProfile(False, True, True)
