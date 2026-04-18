import sqlite3
import tempfile
import os
import pytest
from bot.storage import Storage


@pytest.fixture
def storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = Storage(path)
    s.init_db()
    yield s
    s.close()
    try:
        os.unlink(path)
    except PermissionError:
        pass


def test_init_db_creates_tables(storage):
    with sqlite3.connect(storage.db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    names = [r[0] for r in rows]
    assert "posts" in names
    assert "checked_comments" in names
    assert "flagged_replies" in names
    assert "kv_store" in names


def test_init_db_sets_wal_mode(storage):
    with sqlite3.connect(storage.db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_save_and_get_post(storage):
    storage.save_post(post_id=42, channel_id=-100111, word="leverage", posted_at=1713398400)

    word = storage.get_word_for_post(42)
    assert word == "leverage"


def test_get_word_for_unknown_post_returns_none(storage):
    assert storage.get_word_for_post(999) is None


def test_save_post_is_idempotent(storage):
    storage.save_post(1, -100111, "despite", 1000)
    storage.save_post(1, -100111, "despite", 1000)
    assert storage.get_word_for_post(1) == "despite"
