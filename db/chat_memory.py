"""
db/chat_memory.py

Layer 3: Conversation memory (SQLite).

Every message, from either side, is stored immediately with a session id
and timestamp (see add_message, called right after the user sends a message
and again right after the agent replies -- see app.py). Retention is
enforced explicitly via prune_older_than(), called once per app startup in
app.py's cached _startup(); SQLite does not expire rows on its own.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Tuple

from config import HISTORY_MESSAGES_FOR_CONTEXT, RETENTION_DAYS, SQLITE_DB_PATH
from logging_config import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sender TEXT NOT NULL CHECK (sender IN ('user', 'agent')),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history (session_id, created_at);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the schema if it doesn't exist yet. Safe to call every startup."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.info("chat_memory: schema ready at %s", SQLITE_DB_PATH)


def add_message(session_id: str, sender: str, text: str) -> None:
    """Persist one message immediately. sender is 'user' or 'agent'."""
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_history (session_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
            (session_id, sender, text, now),
        )


def get_all_messages(session_id: str) -> List[Tuple[str, str]]:
    """Full transcript for a session, oldest first, as (sender, text) tuples."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sender, text FROM chat_history WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    return [(r["sender"], r["text"]) for r in rows]


def get_recent_messages(session_id: str, limit: int = HISTORY_MESSAGES_FOR_CONTEXT) -> List[Tuple[str, str]]:
    """Most recent `limit` messages, returned oldest -> newest."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sender, text FROM chat_history WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [(r["sender"], r["text"]) for r in reversed(rows)]


def summarize_recent_history(session_id: str) -> str:
    """Agent 2 (Context Historian) output: a compact text block for the prompt."""
    messages = get_recent_messages(session_id)
    if not messages:
        return "(no prior conversation in this session)"
    lines = []
    for sender, text in messages:
        role = "User" if sender == "user" else "Assistant"
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def list_sessions() -> List[Tuple[str, str, str]]:
    """
    Returns (session_id, preview, last_active) for every session that has at
    least one message, most-recently-active first. `preview` is the text of
    the session's first message, used as the sidebar label in app.py.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT session_id, text, created_at FROM chat_history ORDER BY created_at ASC"
        ).fetchall()

    sessions = {}
    for r in rows:
        sid = r["session_id"]
        if sid not in sessions:
            sessions[sid] = {"preview": r["text"], "last_active": r["created_at"]}
        else:
            sessions[sid]["last_active"] = r["created_at"]

    ordered = sorted(sessions.items(), key=lambda kv: kv[1]["last_active"], reverse=True)
    return [(sid, data["preview"], data["last_active"]) for sid, data in ordered]


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    logger.info("chat_memory: deleted session %s", session_id)


def delete_all() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM chat_history")
    logger.info("chat_memory: deleted ALL chat history")


def prune_older_than(days: int = RETENTION_DAYS) -> int:
    """Delete messages older than `days`. Returns the number of rows deleted."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM chat_history WHERE created_at < ?", (cutoff,))
        deleted = cursor.rowcount
    logger.info("chat_memory: pruned %d message(s) older than %d day(s)", deleted, days)
    return deleted
