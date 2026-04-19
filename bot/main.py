import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.ai_client import GeminiClient
from bot.comment_checker import CommentChecker
from bot.config import Config
from bot.handlers import (
    handle_channel_post,
    handle_discussion_message,
    handle_stats_command,
)
from bot.reporter import build_weekly_report
from bot.storage import Storage


async def main() -> None:
    cfg = Config.load()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("bot")

    storage = Storage(cfg.db_path)
    storage.init_db()

    ai_client = GeminiClient(api_key=cfg.openrouter_api_key, model=cfg.ai_model)
    bot = Bot(token=cfg.tg_bot_token)

    async def send_reply(chat_id: int, reply_to: int, text: str) -> int | None:
        m = await bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to)
        return m.message_id

    checker = CommentChecker(storage=storage, ai_client=ai_client, send_reply=send_reply)

    router = Router()

    # Catch-all: log every update at the dispatcher entry.
    @router.update.outer_middleware()
    async def log_all_updates(handler, event, data):
        try:
            log.info("RAW_UPDATE kind=%s", type(event.model_dump(exclude_none=True)).__name__)
            dump = event.model_dump(exclude_none=True)
            # shallow top-level keys tell us what kind of update
            keys = [k for k in dump.keys() if k != "update_id"]
            log.info("RAW_UPDATE update_id=%s keys=%s", dump.get("update_id"), keys)
        except Exception as e:
            log.warning("RAW_UPDATE logging failed: %s", e)
        return await handler(event, data)

    @router.channel_post()
    async def on_channel_post(msg: Message):
        await handle_channel_post(msg, storage)

    @router.message(F.chat.type.in_({"group", "supergroup"}))
    async def on_discussion(msg: Message):
        await handle_discussion_message(msg, checker)

    @router.message(Command("stats"))
    async def on_stats(msg: Message):
        await handle_stats_command(msg, storage, cfg.teacher_tg_id)

    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=cfg.tz)

    async def send_weekly_report():
        report = build_weekly_report(storage)
        try:
            await bot.send_message(chat_id=cfg.teacher_tg_id, text=report)
        except Exception as e:
            log.warning("Failed to send weekly report: %s", e)

    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=cfg.tz),
    )
    scheduler.start()

    log.info("Bot starting (polling)...")
    # Explicitly request every relevant update type so auto-detection doesn't
    # accidentally drop something (channel_post, edited channel_post, my_chat_member).
    allowed = [
        "message", "edited_message",
        "channel_post", "edited_channel_post",
        "my_chat_member", "chat_member",
    ]
    try:
        await dp.start_polling(bot, allowed_updates=allowed)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        storage.close()


if __name__ == "__main__":
    asyncio.run(main())
