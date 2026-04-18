import tempfile
import os
import time
import pytest
from bot.storage import Storage
from bot.reporter import build_weekly_report


@pytest.fixture
def populated_storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = Storage(path)
    s.init_db()

    now = int(time.time())
    s.save_post(1, -100111, "leverage", now - 86400 * 2)
    s.save_post(2, -100111, "despite", now - 86400 * 4)
    for i in range(10):
        s.save_checked_comment(
            comment_id=100 + i, discussion_group_id=-100222, post_id=1,
            user_id=1, username="u", user_sentence="s",
            is_correct=(i < 6), used_target_word=True, corrected="s",
            explanation_uz="", bot_reply_id=None,
            checked_at=now - i * 3600, ai_cost_usd=0.0003,
        )
    for i in range(5):
        s.save_checked_comment(
            comment_id=200 + i, discussion_group_id=-100222, post_id=2,
            user_id=2, username="v", user_sentence="s",
            is_correct=True, used_target_word=True, corrected="s",
            explanation_uz="", bot_reply_id=None,
            checked_at=now - i * 3600, ai_cost_usd=0.0003,
        )

    yield s
    s.close()
    try:
        os.unlink(path)
    except PermissionError:
        pass


def test_report_includes_totals_and_top_words(populated_storage):
    report = build_weekly_report(populated_storage)

    assert "15" in report
    assert "leverage" in report
    assert "despite" in report
    assert "%" in report


def test_empty_storage_returns_placeholder():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = Storage(path)
    s.init_db()
    try:
        report = build_weekly_report(s)
        assert "yo'q" in report.lower() or "0" in report
    finally:
        s.close()
        try:
            os.unlink(path)
        except PermissionError:
            pass
