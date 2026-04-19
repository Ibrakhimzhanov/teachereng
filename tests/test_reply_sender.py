from bot.ai_client import CheckResult
from bot.reply_sender import format_reply


def test_reply_passes_ai_text_through():
    r = CheckResult(
        is_correct=True,
        used_target_word=True,
        corrected="x",
        explanation_uz="",
        reply_text="Aynan shunday, balli!",
    )
    assert format_reply(r) == "Aynan shunday, balli!"


def test_reply_strips_whitespace():
    r = CheckResult(
        is_correct=False, used_target_word=True, corrected="x", explanation_uz="y",
        reply_text="  \n Deyarli to'g'ri.\n\n",
    )
    assert format_reply(r) == "Deyarli to'g'ri."
