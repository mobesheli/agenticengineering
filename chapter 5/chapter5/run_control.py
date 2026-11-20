"""Controlling one agent run: a turn cap, a time limit, and a plan for each ending."""

from __future__ import annotations

import asyncio
import logging
import sqlite3

from agents import Runner
from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError, ModelRefusalError

from chapter5.investigation import InvestigationResult, investigator

log = logging.getLogger("chapter5.orchestration")

TURN_CAP = 12
TIME_CAP_SECONDS = 120
MAX_RETRIES = 1


class RetryLedger:
    """Counts attempts per case in a database, so the count survives a restart."""

    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS attempts (case_id TEXT PRIMARY KEY, n INTEGER)"
        )

    async def record_attempt(self, case_id: str) -> int:
        self.db.execute(
            "INSERT INTO attempts VALUES (?, 1) "
            "ON CONFLICT (case_id) DO UPDATE SET n = n + 1",
            (case_id,),
        )
        self.db.commit()
        row = self.db.execute("SELECT n FROM attempts WHERE case_id = ?", (case_id,))
        return row.fetchone()[0]


def escalated(case_id: str, reason: str) -> InvestigationResult:
    return InvestigationResult(
        case_id=case_id, status="escalated_to_human", reason=reason
    )


async def run_investigation(
    case_id: str, summary: str, retries: RetryLedger
) -> InvestigationResult:
    try:
        async with asyncio.timeout(TIME_CAP_SECONDS):
            run = await Runner.run(investigator, summary, max_turns=TURN_CAP)
    except (MaxTurnsExceeded, TimeoutError):
        return escalated(case_id, "Budget spent before a conclusion.")
    except ModelRefusalError:
        return escalated(case_id, "The model declined the task.")
    except ModelBehaviorError as err:
        log.warning("malformed output on %s: %s", case_id, err)
        if await retries.record_attempt(case_id) > MAX_RETRIES:
            return escalated(case_id, "Malformed output again after one retry.")
        return InvestigationResult(
            case_id=case_id, status="retry_queued", reason="Malformed output."
        )
    return InvestigationResult(
        case_id=case_id,
        status="concluded",
        reason="Assessment produced; evidence still to be checked.",
        assessment=run.final_output,
    )
