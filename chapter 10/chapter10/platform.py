"""A small stand-in for the shared services an agent meets in production.

Each attribute is one place an operator can act: the model gateway, the identity
directory, the tool contracts, the runtime endpoints, the register, and the data
catalog. The tools and the worker ask this object before they do anything, the
way real ones would ask the real services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chapter10.contracts import Contract


class Refused(Exception):
    """A platform service said no. The message names the service and the reason."""


@dataclass
class Platform:
    agent: str = "maintenance-planner"
    budget_usd: float = 2500.0
    identity_enabled: bool = True
    scopes: dict[str, str] = field(
        default_factory=lambda: {"parts-catalog": "read", "work-orders": "write"}
    )
    contracts: dict[str, Contract] = field(default_factory=dict)
    endpoints: dict[str, str | None] = field(default_factory=dict)
    register_status: str = "listed"
    certified: dict[str, bool] = field(default_factory=dict)
    work_orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    memory_writes: list[dict[str, Any]] = field(default_factory=list)
    audit: list[tuple[str, str]] = field(default_factory=list)

    def note(self, kind: str, detail: str) -> None:
        self.audit.append((kind, detail))

    def admit_model_call(self) -> None:
        if self.budget_usd <= 0:
            self.note("gateway_refused", "budget is zero")
            raise Refused("gateway: budget is zero, model call refused")

    def check_identity(self, service: str, needs: str = "read") -> None:
        """The check the tool server makes itself, whatever the client decided."""
        if not self.identity_enabled:
            self.note("identity_refused", service)
            raise Refused(f"{service}: identity {self.agent} is disabled")
        if needs == "write" and self.scopes.get(service) != "write":
            self.note("server_refused", f"{service}: no write scope for {self.agent}")
            raise Refused(f"{service}: identity {self.agent} has no write scope")

    def check_data(self, product: str) -> None:
        if not self.certified.get(product, False):
            self.note("data_refused", product)
            raise Refused(f"data product {product} is not certified")

    def accepts_runs(self, plant: str) -> bool:
        return self.endpoints.get(plant) is not None

    def on_marketplace(self) -> bool:
        return self.register_status == "listed"
