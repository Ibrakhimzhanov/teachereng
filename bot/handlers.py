import logging
from aiogram.types import Message

from bot.comment_checker import CommentChecker
from bot.post_parser import extract_word
from bot.reporter import build_weekly_report
from bot.storage import Storage

log = logging.getLogger(__name__)


async def handle_channel_post(msg: Message, storage: Storage) -> None:
    text = msg.text or msg.caption or ""
    word = extract_word(text)
    if not word:
        return
    storage.save_post(
        post_id=msg.message_id,
        channel_id=msg.chat.id,
        word=word,
        posted_at=int(msg.date.timestamp()),
    )
    log.info("Saved word '%s' for post %d", word, msg.message_id)


async def handle_discussion_message(msg: Message, checker: CommentChecker) -> None:
    if not msg.text:
        return
    if not msg.reply_to_message:
        return
    channel_post_id = getattr(msg.reply_to_message, "forward_from_message_id", None)
    if not channel_post_id:
        return

    await checker.check(
        comment_id=msg.message_id,
        discussion_group_id=msg.chat.id,
        reply_to_post_id=channel_post_id,
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        text=msg.text,
    )


async def handle_stats_command(msg: Message, storage: Storage, teacher_id: int) -> None:
    if msg.from_user.id != teacher_id:
        return
    report = build_weekly_report(storage)
    await msg.answer(report)
