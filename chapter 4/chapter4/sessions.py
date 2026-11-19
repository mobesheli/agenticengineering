"""Where a conversation lives between turns."""

from __future__ import annotations

from agents import SQLiteSession
from agents.extensions.memory.sqlalchemy_session import SQLAlchemySession


def file_session(session_id: str, db_path: str = "conversations.db") -> SQLiteSession:
    return SQLiteSession(session_id=session_id, db_path=db_path)


def database_session(session_id: str, database_url: str) -> SQLAlchemySession:
    return SQLAlchemySession.from_url(
        session_id=session_id, url=database_url, create_tables=True
    )
