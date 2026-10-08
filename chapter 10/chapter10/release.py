"""Release-bundle identity, durable approval parking, and rollback semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .artifacts import canonical_hash, load_model
from .models import ParkedRun, ReleaseBundle, ResumeResult


def load_bundle(path: Path) -> ReleaseBundle:
    return load_model(path, ReleaseBundle)


def bundle_digest(bundle: ReleaseBundle) -> str:
    return canonical_hash(bundle.model_dump(mode="json"))


class ParkedRunStore:
    """Server-owned teaching store; clients never submit serialized run state."""

    def __init__(self) -> None:
        self._runs: dict[str, ParkedRun] = {}
        self._idempotency_keys: set[str] = set()
        self._lock = Lock()

    def park(
        self,
        *,
        run_id: str,
        bundle: str,
        state: dict[str, Any],
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ParkedRun:
        with self._lock:
            if idempotency_key in self._idempotency_keys:
                raise ValueError("idempotency key already parked")
            parked = ParkedRun(
                run_id=run_id,
                bundle=bundle,
                state=state,
                idempotency_key=idempotency_key,
                parked_at=now or datetime.now(timezone.utc),
            )
            self._runs[run_id] = parked
            self._idempotency_keys.add(idempotency_key)
            return parked

    def resume(
        self, run_id: str, *, current_bundle: str, approved: bool
    ) -> ResumeResult:
        with self._lock:
            parked = self._runs.pop(run_id, None)
        if parked is None:
            return ResumeResult(status="rejected", run_id=run_id, reason="unknown run")
        if parked.bundle != current_bundle:
            return ResumeResult(
                status="stale",
                run_id=run_id,
                reason="release moved while waiting; restart under the current bundle",
            )
        state = dict(parked.state)
        state["approval"] = "approved" if approved else "rejected"
        return ResumeResult(status="resumed", run_id=run_id, state=state)


class ReleasePointer:
    def __init__(self, bundle: str) -> None:
        self.current = bundle
        self.history = [bundle]

    def move(self, bundle: str) -> None:
        if bundle != self.current:
            self.current = bundle
            self.history.append(bundle)

    def rollback(self) -> str:
        if len(self.history) < 2:
            raise RuntimeError("no prior bundle exists")
        self.history.pop()
        self.current = self.history[-1]
        return self.current


ROLLBACK_LIMITS = {
    "memory": "newer summaries remain and must be versioned or quarantined",
    "side_effects": "completed effects require designed compensating actions",
    "in_flight_runs": "parked runs restart when their bundle no longer matches",
}
