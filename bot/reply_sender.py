from bot.ai_client import CheckResult


def format_reply(result: CheckResult) -> str:
    """Return the Telegram reply text. The AI generates a fully-formed,
    varied natural-Uzbek message — we pass it through as-is."""
    return result.reply_text.strip()
