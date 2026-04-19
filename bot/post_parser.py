import re

_STRICT_RE = re.compile(r"#word_([a-zA-Z]+)", re.IGNORECASE)
_SIMPLE_RE = re.compile(r"#([a-zA-Z]{2,})\b")


def extract_word(text: str | None) -> str | None:
    """Find the target word in a teacher's post.

    Priority:
      1. #word_<word> (explicit format, always wins).
      2. If the post has exactly ONE hashtag like #Leverage, use it as the target word.
      3. Otherwise None (ambiguous — bot will not react).
    """
    if not text:
        return None

    m = _STRICT_RE.search(text)
    if m:
        return m.group(1).lower()

    hashtags = _SIMPLE_RE.findall(text)
    if len(hashtags) == 1:
        return hashtags[0].lower()

    return None
