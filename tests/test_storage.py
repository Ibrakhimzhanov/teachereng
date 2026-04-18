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


def test_save_checked_comment_and_query(storage):
    storage.save_post(10, -100111, "leverage", 1000)
    storage.save_checked_comment(
        comment_id=500,
        discussion_group_id=-100222,
        post_id=10,
        user_id=777,
        username="alice",
        user_sentence="I leverage my time.",
        is_correct=True,
        used_target_word=True,
        corrected="I leverage my time.",
        explanation_uz="",
        bot_reply_id=501,
        checked_at=1500,
        ai_cost_usd=0.0003,
    )

    assert storage.was_comment_checked(500) is True
    assert storage.was_comment_checked(999) is False


def test_insert_or_ignore_dedups_comments(storage):
    storage.save_post(10, -100111, "leverage", 1000)
    first = storage.save_checked_comment(
        comment_id=500, discussion_group_id=-100222, post_id=10,
        user_id=777, username="a", user_sentence="x", is_correct=True,
        used_target_word=True, corrected="x", explanation_uz="",
        bot_reply_id=None, checked_at=1500, ai_cost_usd=0.0,
    )
    second = storage.save_checked_comment(
        comment_id=500, discussion_group_id=-100222, post_id=10,
        user_id=777, username="a", user_sentence="x", is_correct=True,
        used_target_word=True, corrected="x", explanation_uz="",
        bot_reply_id=None, checked_at=1500, ai_cost_usd=0.0,
    )
    assert first is True
    assert second is False


def test_stats_last_n_days(storage):
    storage.save_post(10, -100111, "leverage", 1000)
    now = 1_700_000_000
    for i in range(5):
        storage.save_checked_comment(
            comment_id=1000 + i, discussion_group_id=-100222, post_id=10,
            user_id=777, username="u", user_sentence="s", is_correct=(i % 2 == 0),
            used_target_word=True, corrected="s", explanation_uz="",
            bot_reply_id=None, checked_at=now - i * 3600, ai_cost_usd=0.0003,
        )
    stats = storage.stats_since(now - 86400 * 7)
    assert stats["total"] == 5
    assert stats["correct"] == 3
    assert stats["incorrect"] == 2
    assert stats["top_words"][0] == ("leverage", 5)
