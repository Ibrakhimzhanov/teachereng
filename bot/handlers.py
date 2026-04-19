import logging
from aiogram.types import Message

from bot.comment_checker import CommentChecker
from bot.post_parser import extract_word
from bot.reporter import build_weekly_report
from bot.storage import Storage

log = logging.getLogger(__name__)


async def handle_channel_post(msg: Message, storage: Storage) -> None:
    text = msg.text or msg.caption or ""
    log.info(
        "CHANNEL_POST chat_id=%s msg_id=%s title=%r text_preview=%r",
        msg.chat.id, msg.message_id, msg.chat.title, text[:120],
    )
    word = extract_word(text)
    if not word:
        log.info("CHANNEL_POST no target word extracted — ignoring post %d", msg.message_id)
        return
    storage.save_post(
        post_id=msg.message_id,
        channel_id=msg.chat.id,
        word=word,
        posted_at=int(msg.date.timestamp()),
    )
    log.info("Saved word '%s' for post %d", word, msg.message_id)


async def handle_discussion_message(msg: Message, checker: CommentChecker) -> None:
    reply_to = msg.reply_to_message
    fwd_id = getattr(reply_to, "forward_from_message_id", None) if reply_to else None
    log.info(
        "GROUP_MSG chat_id=%s msg_id=%s from_id=%s username=%s has_text=%s has_reply=%s fwd_from_msg=%s text=%r",
        msg.chat.id, msg.message_id,
        getattr(msg.from_user, "id", None),
        getattr(msg.from_user, "username", None),
        bool(msg.text), bool(reply_to), fwd_id,
        (msg.text or "")[:120],
    )
    if not msg.text:
        log.info("GROUP_MSG no text — skip")
        return
    if not reply_to:
        log.info("GROUP_MSG no reply_to_message (not a comment) — skip")
        return
    if not fwd_id:
        log.info("GROUP_MSG reply_to exists but forward_from_message_id is empty — skip")
        return

    await checker.check(
        comment_id=msg.message_id,
        discussion_group_id=msg.chat.id,
        reply_to_post_id=fwd_id,
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        text=msg.text,
    )


async def handle_stats_command(msg: Message, storage: Storage, teacher_id: int) -> None:
    if msg.from_user.id != teacher_id:
        return
    report = build_weekly_report(storage)
    await msg.answer(report)
