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
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        storage.close()


if __name__ == "__main__":
    asyncio.run(main())
