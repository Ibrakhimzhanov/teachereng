import time
from bot.storage import Storage


def build_weekly_report(storage: Storage, now_ts: int | None = None) -> str:
    now = now_ts if now_ts is not None else int(time.time())
    since = now - 86400 * 7
    s = storage.stats_since(since)

    if s["total"] == 0:
        return "📊 Haftalik hisobot\n\nO'tgan haftada tekshirilgan gaplar yo'q."

    correct_pct = round(s["correct"] / s["total"] * 100)
    incorrect_pct = 100 - correct_pct

    lines = [
        "📊 Haftalik hisobot (oxirgi 7 kun)",
        "",
        f"Tekshirilgan: {s['total']} ta gap",
        f"To'g'ri: {s['correct']} ({correct_pct}%)",
        f"Xatolar: {s['incorrect']} ({incorrect_pct}%)",
        "",
        "Top so'zlar:",
    ]
    for word, cnt in s["top_words"]:
        lines.append(f"  • {word} — {cnt} ta")

    return "\n".join(lines)
