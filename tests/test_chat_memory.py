"""
tests/test_chat_memory.py

Covers: schema init, immediate message saving, session listing/preview,
recent-history summarization, session deletion, and retention pruning.
Uses a temporary SQLite file (monkeypatched onto the module) so tests never
touch the real ./history.db.
"""

import uuid
from datetime import datetime, timedelta

import db.chat_memory as chat_memory


def _use_temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_history.db")
    monkeypatch.setattr(chat_memory, "SQLITE_DB_PATH", db_path)
    chat_memory.init_db()
    return db_path


def test_add_and_get_all_messages(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    session_id = str(uuid.uuid4())

    chat_memory.add_message(session_id, "user", "Hello there")
    chat_memory.add_message(session_id, "agent", "Hi! How can I help?")

    messages = chat_memory.get_all_messages(session_id)
    assert messages == [("user", "Hello there"), ("agent", "Hi! How can I help?")]


def test_get_recent_messages_limits_and_orders(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    session_id = str(uuid.uuid4())

    for i in range(8):
        chat_memory.add_message(session_id, "user", f"message {i}")

    recent = chat_memory.get_recent_messages(session_id, limit=5)
    assert [text for _, text in recent] == [f"message {i}" for i in range(3, 8)]


def test_summarize_recent_history_formats_roles(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    session_id = str(uuid.uuid4())

    chat_memory.add_message(session_id, "user", "What is RAG?")
    chat_memory.add_message(session_id, "agent", "Retrieval-augmented generation.")

    summary = chat_memory.summarize_recent_history(session_id)
    assert "User: What is RAG?" in summary
    assert "Assistant: Retrieval-augmented generation." in summary


def test_summarize_recent_history_empty_session(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    summary = chat_memory.summarize_recent_history(str(uuid.uuid4()))
    assert "no prior conversation" in summary


def test_list_sessions_orders_by_last_active(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    chat_memory.add_message(session_a, "user", "First session message")
    chat_memory.add_message(session_b, "user", "Second session message")
    chat_memory.add_message(session_a, "user", "Back to session A")

    sessions = chat_memory.list_sessions()
    session_ids_in_order = [s[0] for s in sessions]
    assert session_ids_in_order[0] == session_a  # most recently active first

    preview_by_id = {sid: preview for sid, preview, _ in sessions}
    assert preview_by_id[session_a] == "First session message"


def test_delete_session_removes_only_that_session(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    chat_memory.add_message(session_a, "user", "keep me... wait, delete me")
    chat_memory.add_message(session_b, "user", "keep me")

    chat_memory.delete_session(session_a)

    assert chat_memory.get_all_messages(session_a) == []
    assert len(chat_memory.get_all_messages(session_b)) == 1


def test_delete_all_clears_every_session(tmp_path, monkeypatch):
    _use_temp_db(tmp_path, monkeypatch)
    chat_memory.add_message(str(uuid.uuid4()), "user", "hello")
    chat_memory.add_message(str(uuid.uuid4()), "user", "world")

    chat_memory.delete_all()

    assert chat_memory.list_sessions() == []


def test_prune_older_than_deletes_old_rows_only(tmp_path, monkeypatch):
    db_path = _use_temp_db(tmp_path, monkeypatch)
    session_id = str(uuid.uuid4())

    # Insert one "old" row directly (bypassing add_message's utcnow()) and
    # one fresh row via add_message.
    import sqlite3

    old_timestamp = (datetime.utcnow() - timedelta(days=40)).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO chat_history (session_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
        (session_id, "user", "an old message", old_timestamp),
    )
    conn.commit()
    conn.close()

    chat_memory.add_message(session_id, "user", "a fresh message")

    deleted = chat_memory.prune_older_than(days=30)
    assert deleted == 1

    remaining = chat_memory.get_all_messages(session_id)
    assert remaining == [("user", "a fresh message")]
