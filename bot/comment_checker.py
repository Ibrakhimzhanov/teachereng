import logging
import re
import time
from typing import Awaitable, Callable

from bot.ai_client import GeminiClient
from bot.reply_sender import format_reply
from bot.storage import Storage

log = logging.getLogger(__name__)


SendReplyFn = Callable[[int, int, str], Awaitable[int | None]]


_UZBEK_MARKERS = {
    "men", "sen", "biz", "siz", "bu", "shu", "uchun", "bilan",
    "ham", "emas", "bor", "yoq", "yo'q", "yoki", "juda", "lekin",
    "qiladi", "qilaman", "qilish", "bo'ladi", "bo'lgan",
    "ishlataman", "ishlat", "o'sha", "shunday", "kelaman",
    "kelishi", "bilaman", "bilmayman", "bilmadim",
    "ingliz", "tili", "so'z", "so'zi", "so'zini", "so'zini", "misol",
}

_ENGLISH_MARKERS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "done",
    "will", "would", "can", "could", "should", "shall", "may", "might", "must",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their",
    "this", "that", "these", "those",
    "and", "but", "or", "if", "because", "though", "although", "while",
    "of", "in", "to", "for", "with", "on", "at", "by", "from", "about",
    "not", "no", "yes",
    "like", "want", "need", "go", "goes", "going", "went", "come", "comes",
    "make", "makes", "made", "get", "gets", "got", "use", "uses", "used",
    "say", "said", "see", "saw", "seen", "know", "knew", "known",
    "think", "thought", "take", "took", "taken", "give", "gave", "given",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


# Uzbek-specific: "o'" or "g'" (as in so'z, o'qituvchi, og'ir, yo'q).
# Matches all common apostrophe variants (ASCII ', curly ', Unicode modifier letters).
# Does NOT match English contractions like "I'm", "don't", "John's".
_UZBEK_APOSTROPHE_RE = re.compile(
    r"[og][\u0027\u2019\u2018\u02bc\u02bb\u0060]",
    re.IGNORECASE,
)


def is_probably_english(text: str) -> bool:
    if not text or not text.strip():
        return False

    if _UZBEK_APOSTROPHE_RE.search(text):
        return False

    tokens = _tokens(text)
    if not tokens:
        return False

    if any(tok in _UZBEK_MARKERS for tok in tokens):
        return False

    if any(tok in _ENGLISH_MARKERS for tok in tokens):
        return True

    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if "a" <= c.lower() <= "z")
    return (latin / len(letters)) >= 0.80


class CommentChecker:
    def __init__(self, storage: Storage, ai_client: GeminiClient, send_reply: SendReplyFn):
        self._storage = storage
        self._ai = ai_client
        self._send = send_reply

    async def check(
        self,
        *,
        comment_id: int,
        discussion_group_id: int,
        reply_to_post_id: int,
        user_id: int,
        username: str | None,
        text: str,
    ) -> None:
        if self._storage.was_comment_checked(comment_id):
            return

        word = self._storage.get_word_for_post(reply_to_post_id)
        if not word:
            return

        if not is_probably_english(text):
            log.info("Skipping non-English comment %d", comment_id)
            return

        try:
            result, cost = await self._ai.check_sentence(word, text)
        except Exception as e:
            log.warning("AI failed for comment %d: %s", comment_id, e)
            return

        reply_text = format_reply(result)
        bot_reply_id: int | None = None
        try:
            bot_reply_id = await self._send(discussion_group_id, comment_id, reply_text)
        except Exception as e:
            log.warning("Failed to send reply for comment %d: %s", comment_id, e)

        self._storage.save_checked_comment(
            comment_id=comment_id,
            discussion_group_id=discussion_group_id,
            post_id=reply_to_post_id,
            user_id=user_id,
            username=username,
            user_sentence=text,
            is_correct=result.is_correct,
            used_target_word=result.used_target_word,
            corrected=result.corrected,
            explanation_uz=result.explanation_uz,
            bot_reply_id=bot_reply_id,
            checked_at=int(time.time()),
            ai_cost_usd=cost,
        )
