import tempfile
import os
import time
from unittest.mock import AsyncMock, MagicMock
import pytest

from bot.ai_client import CheckResult
from bot.comment_checker import CommentChecker, is_probably_english
from bot.storage import Storage


def test_english_sentence_detected():
    assert is_probably_english("I can leverage my time to study.") is True


def test_uzbek_ignored():
    assert is_probably_english("Men leverage so'zini bilaman") is False


def test_russian_ignored():
    assert is_probably_english("Я использую leverage каждый день") is False


def test_mixed_below_threshold():
    assert is_probably_english("bu leverage so'zi uchun misol") is False


def test_empty_string_not_english():
    assert is_probably_english("") is False
    assert is_probably_english("   ") is False


def test_english_contractions_are_english():
    # Regression: "I'm", "don't", "it's" — apostrophes in English must NOT trip Uzbek detector.
    assert is_probably_english("I'm leveraging my knowledge to useful activities.") is True
    assert is_probably_english("Don't give up on your dreams.") is True
    assert is_probably_english("It's a great day to learn English.") is True
    assert is_probably_english("John's book is on the table.") is True


def test_uzbek_apostrophe_pattern_detected():
    assert is_probably_english("o'qituvchi ingliz tilini o'rgatadi") is False
    assert is_probably_english("og'ir vaziyat") is False


@pytest.fixture
def checker_env():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    storage = Storage(path)
    storage.init_db()
    storage.save_post(100, -100111, "leverage", int(time.time()))

    ai = MagicMock()
    ai.check_sentence = AsyncMock(return_value=(
        CheckResult(is_correct=True, used_target_word=True,
                    corrected="I leverage my time.", explanation_uz="",
                    reply_text="Aynan shunday, balli!"),
        0.0003,
    ))

    sender = AsyncMock(return_value=9999)

    checker = CommentChecker(storage=storage, ai_client=ai, send_reply=sender)

    yield {"checker": checker, "storage": storage, "ai": ai, "sender": sender}

    storage.close()
    try:
        os.unlink(path)
    except PermissionError:
        pass


@pytest.mark.asyncio
async def test_skips_when_no_word_for_post(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=1, discussion_group_id=-100222,
        reply_to_post_id=999,
        user_id=1, username="a", text="I leverage time.",
    )
    checker_env["ai"].check_sentence.assert_not_called()


@pytest.mark.asyncio
async def test_skips_non_english(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=2, discussion_group_id=-100222,
        reply_to_post_id=100,
        user_id=1, username="a", text="Men leverage so'zini bilaman",
    )
    checker_env["ai"].check_sentence.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_calls_ai_and_sends_reply(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=3, discussion_group_id=-100222,
        reply_to_post_id=100,
        user_id=1, username="alice", text="I leverage my time.",
    )
    checker_env["ai"].check_sentence.assert_awaited_once_with("leverage", "I leverage my time.")
    checker_env["sender"].assert_awaited_once()
    assert checker_env["storage"].was_comment_checked(3)


@pytest.mark.asyncio
async def test_dedup_does_not_recheck(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=4, discussion_group_id=-100222, reply_to_post_id=100,
        user_id=1, username="a", text="I leverage time.",
    )
    await c.check(
        comment_id=4, discussion_group_id=-100222, reply_to_post_id=100,
        user_id=1, username="a", text="I leverage time.",
    )
    assert checker_env["ai"].check_sentence.await_count == 1
