from bot.ai_client import CheckResult
from bot.reply_sender import format_reply


def test_correct_reply_is_short():
    r = CheckResult(is_correct=True, used_target_word=True, corrected="x", explanation_uz="")
    text = format_reply(r)
    assert "Zo'r" in text or "To'g'ri" in text
    assert len(text) < 100


def test_error_reply_has_correction_and_uzbek():
    r = CheckResult(
        is_correct=False,
        used_target_word=True,
        corrected="I leverage my English skills to get a better job.",
        explanation_uz="'leveraging' o'rniga 'leverage' ishlating — 'can' dan keyin infinitiv keladi.",
    )
    text = format_reply(r)
    assert "leverage my English skills" in text
    assert "infinitiv" in text
    assert "Tushuntirish" in text


def test_missing_word_reply_reminds_to_use_it():
    r = CheckResult(
        is_correct=False, used_target_word=False,
        corrected="I like apples.",
        explanation_uz="Maqsadli so'z 'leverage' ishlatilmagan. Gapga kiritib ko'ring.",
    )
    text = format_reply(r)
    assert "ishlat" in text.lower()
