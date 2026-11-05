"""The refund store. The idempotency guarantee lives in the database.

The chapter's point is that deduplication must be atomic. A check-then-act
sequence in application code races under concurrent retries; a unique
constraint plus an insert-on-conflict statement does not. ``create_refund_atomic``
is that statement, in one transaction, followed by a read of the winning row.

``db`` hands every thread its own sqlite connection to one shared database
file, so concurrent callers (the tests use real threads) contend on the
database's lock rather than on a Python object. The default file lives in the
system temp directory and is removed at exit; set ``CH3_REFUNDS_DB`` to keep a
store across processes.
"""

from __future__ import annotations

import atexit
import os
import secrets
import sqlite3
import tempfile
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RefundRow:
    """One row of the refunds table plus whether this call created it."""

    refund_id: str
    amount_cents: int
    replayed: bool


class ThreadLocalConnection:
    """One sqlite connection per thread, all on the same database file.

    Supports the two operations the store needs: ``db.execute(...)`` and
    ``with db:`` for a commit-or-rollback transaction on the calling thread's
    connection.
    """

    def __init__(self, path: Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = path
        self._timeout = timeout_seconds
        self._local = threading.local()
        self._all: list[sqlite3.Connection] = []
        self._lock = threading.Lock()

    def _connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.path, timeout=self._timeout, check_same_thread=False
            )
            self._local.conn = conn
            with self._lock:
                self._all.append(conn)
        return conn

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute one statement on the calling thread's connection."""
        return self._connection().execute(sql, parameters)

    def __enter__(self) -> sqlite3.Connection:
        return self._connection().__enter__()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._connection().__exit__(exc_type, exc, tb)

    def close_all(self) -> None:
        """Close every connection this object has opened, on any thread."""
        with self._lock:
            for conn in self._all:
                conn.close()
            self._all.clear()
        self._local = threading.local()


def _default_db_path() -> Path:
    configured = os.environ.get("CH3_REFUNDS_DB")
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / f"ch3-refunds-{os.getpid()}.sqlite"


def _remove_default_file() -> None:
    db.close_all()
    if "CH3_REFUNDS_DB" not in os.environ:
        try:
            db.path.unlink()
        except FileNotFoundError:
            pass


db = ThreadLocalConnection(_default_db_path())
atexit.register(_remove_default_file)

# payments.py (companion code). The guarantee lives in the database.
db.execute("""CREATE TABLE IF NOT EXISTS refunds (
    idempotency_key TEXT PRIMARY KEY, refund_id TEXT NOT NULL,
    charge_id TEXT NOT NULL, amount_cents INTEGER NOT NULL,
    actor_id TEXT NOT NULL, reason TEXT NOT NULL)""")


_refund_ids: Iterator[str] | None = None


def set_refund_id_source(ids: Iterable[str] | None) -> None:
    """Make refund identifiers predictable, for drills and tests.

    Pass ``None`` to go back to random identifiers.
    """
    global _refund_ids
    _refund_ids = iter(ids) if ids is not None else None


def new_refund_id() -> str:
    """Mint a refund identifier such as ``rf_7f3a9c``."""
    if _refund_ids is not None:
        try:
            return next(_refund_ids)
        except StopIteration:
            pass
    return f"rf_{secrets.token_hex(3)}"


def create_refund_atomic(*, idempotency_key, charge_id, amount_cents,
                         actor_id, reason) -> RefundRow:
    with db:  # one transaction
        cursor = db.execute(
            "INSERT INTO refunds VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (idempotency_key) DO NOTHING",
            (idempotency_key, new_refund_id(), charge_id,
             amount_cents, actor_id, reason))
        row = db.execute("SELECT refund_id, amount_cents FROM refunds "
                         "WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    return RefundRow(*row, replayed=(cursor.rowcount == 0))


def count_refunds() -> int:
    """Return the number of refunds in the store."""
    return int(db.execute("SELECT COUNT(*) FROM refunds").fetchone()[0])


def reset_store() -> None:
    """Empty the refunds table. Drills and tests start from a clean store."""
    with db:
        db.execute("DELETE FROM refunds")
