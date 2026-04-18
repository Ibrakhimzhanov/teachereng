import tempfile
import os
import time
from unittest.mock import MagicMock, AsyncMock
import pytest

from bot.handlers import (
    handle_channel_post,
    handle_discussion_message,
    handle_stats_command,
)
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


@pytest.mark.asyncio
async def test_channel_post_with_hashtag_saves_word(storage):
    msg = MagicMock()
    msg.message_id = 42
    msg.chat.id = -100111
    msg.text = "Word of the day #word_leverage"
    msg.caption = None
    msg.date.timestamp.return_value = 1000.0

    await handle_channel_post(msg, storage)

    assert storage.get_word_for_post(42) == "leverage"


@pytest.mark.asyncio
async def test_channel_post_without_hashtag_ignored(storage):
    msg = MagicMock()
    msg.message_id = 43
    msg.chat.id = -100111
    msg.text = "Just a regular post"
    msg.caption = None
    msg.date.timestamp.return_value = 1000.0

    await handle_channel_post(msg, storage)

    assert storage.get_word_for_post(43) is None


@pytest.mark.asyncio
async def test_channel_post_uses_caption_if_no_text(storage):
    msg = MagicMock()
    msg.message_id = 44
    msg.chat.id = -100111
    msg.text = None
    msg.caption = "Photo post #word_despite"
    msg.date.timestamp.return_value = 1000.0

    await handle_channel_post(msg, storage)

    assert storage.get_word_for_post(44) == "despite"


@pytest.mark.asyncio
async def test_discussion_message_resolves_post_and_calls_checker(storage):
    storage.save_post(77, -100111, "achieve", int(time.time()))

    checker = MagicMock()
    checker.check = AsyncMock()

    msg = MagicMock()
    msg.message_id = 500
    msg.chat.id = -100222
    msg.from_user.id = 999
    msg.from_user.username = "student1"
    msg.text = "I achieve my goals."
    msg.reply_to_message.forward_from_message_id = 77

    await handle_discussion_message(msg, checker)

    checker.check.assert_awaited_once()
    kwargs = checker.check.await_args.kwargs
    assert kwargs["comment_id"] == 500
    assert kwargs["reply_to_post_id"] == 77
    assert kwargs["text"] == "I achieve my goals."


@pytest.mark.asyncio
async def test_discussion_message_without_reply_chain_ignored(storage):
    checker = MagicMock()
    checker.check = AsyncMock()

    msg = MagicMock()
    msg.reply_to_message = None
    msg.text = "random comment"

    await handle_discussion_message(msg, checker)

    checker.check.assert_not_called()


@pytest.mark.asyncio
async def test_discussion_message_without_text_ignored(storage):
    checker = MagicMock()
    checker.check = AsyncMock()

    msg = MagicMock()
    msg.text = None
    msg.reply_to_message.forward_from_message_id = 77

    await handle_discussion_message(msg, checker)

    checker.check.assert_not_called()


@pytest.mark.asyncio
async def test_stats_command_sends_report_to_teacher(storage):
    msg = MagicMock()
    msg.from_user.id = 42
    msg.answer = AsyncMock()

    await handle_stats_command(msg, storage, teacher_id=42)

    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "hisobot" in text.lower()


@pytest.mark.asyncio
async def test_stats_command_ignored_for_non_teacher(storage):
    msg = MagicMock()
    msg.from_user.id = 99
    msg.answer = AsyncMock()

    await handle_stats_command(msg, storage, teacher_id=42)
    msg.answer.assert_not_called()
