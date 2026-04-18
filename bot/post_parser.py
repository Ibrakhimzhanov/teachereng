import re

_WORD_RE = re.compile(r"#word_([a-zA-Z]+)", re.IGNORECASE)


def extract_word(text: str | None) -> str | None:
    if not text:
        return None
    m = _WORD_RE.search(text)
    return m.group(1).lower() if m else None
