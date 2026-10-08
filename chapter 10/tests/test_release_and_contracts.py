from __future__ import annotations

from datetime import datetime, timezone

import pytest

from chapter10.artifacts import TEMPLATE_ROOT
from chapter10.contracts import ContractEnforcer, ContractHook
from chapter10.release import (
    ROLLBACK_LIMITS,
    ParkedRunStore,
    ReleasePointer,
    bundle_digest,
    load_bundle,
)


def test_bundle_is_immutable_and_has_fallback_evidence() -> None:
    bundle = load_bundle(TEMPLATE_ROOT / "bundle.yaml")
    assert bundle.bundle == "maintenance-planner@41.3"
    assert "@sha256:" in bundle.image
    assert bundle.model.fallback.golden_pass >= bundle.model.fallback.floor
    assert len(bundle_digest(bundle)) == 64


def test_contract_allows_declared_read_and_denies_write() -> None:
    enforcer = ContractEnforcer.from_directory(TEMPLATE_ROOT / "contracts")
    allowed = enforcer.enforce("parts.catalog.lookup", "search_parts")
    assert allowed.trace_note == "contract:parts.catalog.lookup@3.2.0"
    with pytest.raises(PermissionError, match="outside contract"):
        enforcer.enforce("parts.catalog.lookup", "create_order")
    with pytest.raises(PermissionError, match="no contract"):
        enforcer.enforce("shadow.tool", "read")


@pytest.mark.asyncio
async def test_sdk_shaped_hook_records_contract_version() -> None:
    notes: list[str] = []

    class RunContext:
        def trace_note(self, note: str) -> None:
            notes.append(note)

    class Context:
        def __init__(self) -> None:
            self.tool_arguments = {"operation": "get_lead_time"}
            self.context = RunContext()

    class Tool:
        name = "parts.catalog.lookup"

    hook = ContractHook(ContractEnforcer.from_directory(TEMPLATE_ROOT / "contracts"))
    await hook.on_tool_start(Context(), object(), Tool())
    assert notes == ["contract:parts.catalog.lookup@3.2.0"]


def test_parked_run_resumes_only_under_its_release() -> None:
    store = ParkedRunStore()
    store.park(
        run_id="run-1",
        bundle="maintenance-planner@41.3",
        state={"pending_tool": "create_work_order"},
        idempotency_key="work-order:42",
        now=datetime(2026, 10, 8, tzinfo=timezone.utc),
    )
    stale = store.resume(
        "run-1", current_bundle="maintenance-planner@41.4", approved=True
    )
    assert stale.status == "stale"
    assert "restart" in stale.reason


def test_idempotency_key_is_persisted_before_effect() -> None:
    store = ParkedRunStore()
    arguments = {
        "run_id": "run-1",
        "bundle": "maintenance-planner@41.3",
        "state": {},
        "idempotency_key": "work-order:42",
    }
    store.park(**arguments)
    with pytest.raises(ValueError, match="idempotency"):
        store.park(**{**arguments, "run_id": "run-2"})


def test_release_pointer_rolls_back_but_names_irreversible_state() -> None:
    pointer = ReleasePointer("maintenance-planner@41.2")
    pointer.move("maintenance-planner@41.3")
    assert pointer.rollback() == "maintenance-planner@41.2"
    assert set(ROLLBACK_LIMITS) == {"memory", "side_effects", "in_flight_runs"}
