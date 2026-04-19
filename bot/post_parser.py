import re

# Multi-word phrases use underscores: #word_look_up -> "look up", #word_give_up_on -> "give up on"
_STRICT_RE = re.compile(r"#word_+([a-zA-Z][a-zA-Z_]*)", re.IGNORECASE)
_SIMPLE_RE = re.compile(r"#([a-zA-Z][a-zA-Z_]+)")


def _normalize(raw: str) -> str:
    # Collapse runs of underscores, strip edges, then _ -> space
    cleaned = re.sub(r"_+", "_", raw).strip("_")
    return cleaned.replace("_", " ").lower()


def extract_word(text: str | None) -> str | None:
    """Find the target word / phrase in a teacher's post.

    Priority:
      1. #word_<word> or #word_give_up_on (explicit format, wins).
      2. Single hashtag in the post (#Leverage or #give_up) -> target.
      3. Otherwise None (ambiguous — bot will not react).

    Underscores in the hashtag map to spaces, so phrasal verbs work.
    """
    if not text:
        return None

    m = _STRICT_RE.search(text)
    if m:
        normalized = _normalize(m.group(1))
        return normalized or None

    # Ignore meta-hashtags like #word or #word_something in the fallback branch —
    # if strict didn't match, those are garbage (incomplete markers).
    hashtags = [h for h in _SIMPLE_RE.findall(text) if not h.lower().startswith("word")]
    if len(hashtags) == 1:
        normalized = _normalize(hashtags[0])
        return normalized or None

    return None
