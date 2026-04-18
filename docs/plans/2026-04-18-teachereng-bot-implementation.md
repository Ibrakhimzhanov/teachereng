# teachereng Bot Implementation Plan

> **For Claude:** REQUIRED: Use /superpower-execute-plan to implement this plan task-by-task.

**Goal:** Build a Telegram bot that watches an English-teacher's channel, detects "word of the day" posts (marked with `#word_<word>`), and auto-replies to every student comment with either praise (correct English) or a correction + Uzbek explanation (wrong English).

**Architecture:** Single Python process, aiogram 3 polling, SQLite for persistence, Gemini 3.1 Flash Lite with structured output for checking sentences, APScheduler for weekly teacher reports. Deployed on dev-server `164.92.199.126` via systemd and `git pull`.

**Tech Stack:** Python 3.11, aiogram 3.x, google-genai SDK, SQLite (stdlib), APScheduler, Pydantic, pytest, python-dotenv.

**Reference design:** [`docs/plans/2026-04-18-teachereng-bot-design.md`](2026-04-18-teachereng-bot-design.md)

---

## Conventions for every task

- All commits authored by user only (no Co-authored-by trailer) — see global CLAUDE.md.
- Commit after EVERY task. No batching.
- Never edit files on server directly — only `git pull` + `systemctl restart`.
- Tests live in `tests/` mirroring `bot/` structure.
- Use `sqlite3` stdlib (no ORM — overkill for 4 tables).
- Run tests: `pytest -v` from repo root.

---

## Phase 1 — Scaffolding

### Task 1: Repo hygiene files

**Files:**
- Create: `.gitignore`
- Create: `README.md`

**Step 1: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/

# Environment
.env
.env.local

# SQLite
data.db
data.db-wal
data.db-shm
*.db

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

**Step 2: Write minimal `README.md`**

```markdown
# teachereng

AI-bot for Telegram English-learning channel. Auto-checks student sentences in comments, replies with praise or correction + Uzbek explanation.

See [docs/plans/2026-04-18-teachereng-bot-design.md](docs/plans/2026-04-18-teachereng-bot-design.md) for design and [docs/plans/2026-04-18-teachereng-bot-implementation.md](docs/plans/2026-04-18-teachereng-bot-implementation.md) for implementation plan.

## Quick start

1. `python3 -m venv .venv && source .venv/bin/activate` (bash) or `.venv\Scripts\activate` (Windows)
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in tokens
4. `python -m bot.main`

## Deploy

See [deployment section in implementation plan](docs/plans/2026-04-18-teachereng-bot-implementation.md#phase-4--deployment).
```

**Step 3: Commit**

```bash
git add .gitignore README.md
git commit -m "chore: add .gitignore and README"
```

---

### Task 2: requirements.txt

**Files:**
- Create: `requirements.txt`

**Step 1: Write requirements**

```
aiogram==3.13.1
google-genai==0.3.0
pydantic==2.9.2
python-dotenv==1.0.1
APScheduler==3.10.4
pytz==2024.2

# dev
pytest==8.3.3
pytest-asyncio==0.24.0
```

**Step 2: Verify install works locally**

```bash
python3 -m venv .venv
source .venv/Scripts/activate  # Windows bash
pip install -r requirements.txt
```
Expected: all packages install without errors.

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add Python dependencies"
```

---

### Task 3: .env.example

**Files:**
- Create: `.env.example`

**Step 1: Write template**

```
# Telegram
TG_BOT_TOKEN=123456:ABC-example_token_from_botfather
CHANNEL_ID=-1001234567890
DISCUSSION_GROUP_ID=-1009876543210
TEACHER_TG_ID=123456789

# Gemini
GEMINI_API_KEY=your_gemini_api_key_from_ai_studio

# Misc
TZ=Asia/Tashkent
DB_PATH=data.db
LOG_LEVEL=INFO
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add .env.example with all required vars"
```

---

### Task 4: Project skeleton

**Files:**
- Create: `bot/__init__.py`
- Create: `tests/__init__.py`
- Create: `systemd/` (empty directory placeholder)
- Create: `pytest.ini`

**Step 1: Create empty `bot/__init__.py` and `tests/__init__.py`**

Both files empty.

**Step 2: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
markers =
    integration: integration tests hitting real APIs (opt-in)
```

**Step 3: Verify pytest discovery**

```bash
pytest --collect-only
```
Expected: "collected 0 items" (no tests yet, but no config errors).

**Step 4: Commit**

```bash
git add bot/__init__.py tests/__init__.py pytest.ini
git commit -m "chore: scaffold project structure and pytest config"
```

---

## Phase 2 — Core modules (TDD)

### Task 5: config module

**Files:**
- Create: `bot/config.py`
- Create: `tests/test_config.py`

**Step 1: Write failing test**

```python
# tests/test_config.py
import os
import pytest
from bot.config import Config


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "abc")
    monkeypatch.setenv("CHANNEL_ID", "-100111")
    monkeypatch.setenv("DISCUSSION_GROUP_ID", "-100222")
    monkeypatch.setenv("TEACHER_TG_ID", "333")
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    cfg = Config.load()

    assert cfg.tg_bot_token == "abc"
    assert cfg.channel_id == -100111
    assert cfg.discussion_group_id == -100222
    assert cfg.teacher_tg_id == 333
    assert cfg.gemini_api_key == "key"
    assert cfg.db_path == "data.db"  # default
    assert cfg.tz == "Asia/Tashkent"  # default


def test_config_fail_fast_if_missing(monkeypatch):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TG_BOT_TOKEN"):
        Config.load()
```

**Step 2: Run — expect fail**

```bash
pytest tests/test_config.py -v
```
Expected: `ImportError: cannot import name 'Config'`.

**Step 3: Implement `bot/config.py`**

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    tg_bot_token: str
    channel_id: int
    discussion_group_id: int
    teacher_tg_id: int
    gemini_api_key: str
    db_path: str
    tz: str
    log_level: str

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()

        def req(name: str) -> str:
            val = os.environ.get(name)
            if not val:
                raise RuntimeError(f"Missing required env var: {name}")
            return val

        return cls(
            tg_bot_token=req("TG_BOT_TOKEN"),
            channel_id=int(req("CHANNEL_ID")),
            discussion_group_id=int(req("DISCUSSION_GROUP_ID")),
            teacher_tg_id=int(req("TEACHER_TG_ID")),
            gemini_api_key=req("GEMINI_API_KEY"),
            db_path=os.environ.get("DB_PATH", "data.db"),
            tz=os.environ.get("TZ", "Asia/Tashkent"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
```

**Step 4: Run — expect pass**

```bash
pytest tests/test_config.py -v
```
Expected: 2 passed.

**Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat(config): load settings from .env with fail-fast validation"
```

---

### Task 6: storage — schema + init_db

**Files:**
- Create: `bot/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write failing test**

```python
# tests/test_storage.py
import sqlite3
import tempfile
import os
import pytest
from bot.storage import Storage


@pytest.fixture
def storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = Storage(path)
    s.init_db()
    yield s
    s.close()
    os.unlink(path)


def test_init_db_creates_tables(storage):
    with sqlite3.connect(storage.db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    names = [r[0] for r in rows]
    assert "posts" in names
    assert "checked_comments" in names
    assert "flagged_replies" in names
    assert "kv_store" in names


def test_init_db_sets_wal_mode(storage):
    with sqlite3.connect(storage.db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
```

**Step 2: Run — expect fail**

```bash
pytest tests/test_storage.py -v
```
Expected: `ImportError`.

**Step 3: Implement `bot/storage.py`**

```python
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    post_id    INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    word       TEXT NOT NULL,
    posted_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_word ON posts(word);

CREATE TABLE IF NOT EXISTS checked_comments (
    comment_id          INTEGER PRIMARY KEY,
    discussion_group_id INTEGER NOT NULL,
    post_id             INTEGER NOT NULL,
    user_id             INTEGER NOT NULL,
    username            TEXT,
    user_sentence       TEXT NOT NULL,
    is_correct          INTEGER NOT NULL,
    used_target_word    INTEGER NOT NULL,
    corrected           TEXT,
    explanation_uz      TEXT,
    bot_reply_id        INTEGER,
    checked_at          INTEGER NOT NULL,
    ai_cost_usd         REAL
);
CREATE INDEX IF NOT EXISTS idx_checked_post ON checked_comments(post_id);
CREATE INDEX IF NOT EXISTS idx_checked_at ON checked_comments(checked_at);
CREATE INDEX IF NOT EXISTS idx_checked_user ON checked_comments(user_id);

CREATE TABLE IF NOT EXISTS flagged_replies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id  INTEGER NOT NULL,
    reported_by INTEGER NOT NULL,
    reported_at INTEGER NOT NULL,
    reviewed    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kv_store (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.executescript("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA)
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, isolation_level=None)
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
```

**Step 4: Run — expect pass**

```bash
pytest tests/test_storage.py -v
```
Expected: 2 passed.

**Step 5: Commit**

```bash
git add bot/storage.py tests/test_storage.py
git commit -m "feat(storage): schema, WAL mode, init_db"
```

---

### Task 7: storage — posts CRUD

**Files:**
- Modify: `bot/storage.py`
- Modify: `tests/test_storage.py`

**Step 1: Write failing tests** (append to `tests/test_storage.py`)

```python
def test_save_and_get_post(storage):
    storage.save_post(post_id=42, channel_id=-100111, word="leverage", posted_at=1713398400)

    word = storage.get_word_for_post(42)
    assert word == "leverage"


def test_get_word_for_unknown_post_returns_none(storage):
    assert storage.get_word_for_post(999) is None


def test_save_post_is_idempotent(storage):
    storage.save_post(1, -100111, "despite", 1000)
    storage.save_post(1, -100111, "despite", 1000)  # INSERT OR REPLACE
    assert storage.get_word_for_post(1) == "despite"
```

**Step 2: Run — expect fail**

```bash
pytest tests/test_storage.py -v
```
Expected: `AttributeError: 'Storage' object has no attribute 'save_post'`.

**Step 3: Add methods to `bot/storage.py`**

```python
    def save_post(self, post_id: int, channel_id: int, word: str, posted_at: int) -> None:
        self._connect().execute(
            "INSERT OR REPLACE INTO posts (post_id, channel_id, word, posted_at) VALUES (?, ?, ?, ?)",
            (post_id, channel_id, word.lower(), posted_at),
        )

    def get_word_for_post(self, post_id: int) -> str | None:
        row = self._connect().execute(
            "SELECT word FROM posts WHERE post_id=?", (post_id,)
        ).fetchone()
        return row[0] if row else None
```

**Step 4: Run — expect pass**

```bash
pytest tests/test_storage.py -v
```
Expected: 5 passed.

**Step 5: Commit**

```bash
git add bot/storage.py tests/test_storage.py
git commit -m "feat(storage): save_post and get_word_for_post"
```

---

### Task 8: storage — checked_comments CRUD + stats

**Files:**
- Modify: `bot/storage.py`
- Modify: `tests/test_storage.py`

**Step 1: Write failing tests**

```python
def test_save_checked_comment_and_query(storage):
    storage.save_post(10, -100111, "leverage", 1000)
    storage.save_checked_comment(
        comment_id=500,
        discussion_group_id=-100222,
        post_id=10,
        user_id=777,
        username="alice",
        user_sentence="I leverage my time.",
        is_correct=True,
        used_target_word=True,
        corrected="I leverage my time.",
        explanation_uz="",
        bot_reply_id=501,
        checked_at=1500,
        ai_cost_usd=0.0003,
    )

    assert storage.was_comment_checked(500) is True
    assert storage.was_comment_checked(999) is False


def test_insert_or_ignore_dedups_comments(storage):
    storage.save_post(10, -100111, "leverage", 1000)
    first = storage.save_checked_comment(
        comment_id=500, discussion_group_id=-100222, post_id=10,
        user_id=777, username="a", user_sentence="x", is_correct=True,
        used_target_word=True, corrected="x", explanation_uz="",
        bot_reply_id=None, checked_at=1500, ai_cost_usd=0.0,
    )
    second = storage.save_checked_comment(
        comment_id=500, discussion_group_id=-100222, post_id=10,
        user_id=777, username="a", user_sentence="x", is_correct=True,
        used_target_word=True, corrected="x", explanation_uz="",
        bot_reply_id=None, checked_at=1500, ai_cost_usd=0.0,
    )
    assert first is True
    assert second is False  # already existed


def test_stats_last_n_days(storage):
    storage.save_post(10, -100111, "leverage", 1000)
    now = 1_700_000_000
    for i in range(5):
        storage.save_checked_comment(
            comment_id=1000 + i, discussion_group_id=-100222, post_id=10,
            user_id=777, username="u", user_sentence="s", is_correct=(i % 2 == 0),
            used_target_word=True, corrected="s", explanation_uz="",
            bot_reply_id=None, checked_at=now - i * 3600, ai_cost_usd=0.0003,
        )
    stats = storage.stats_since(now - 86400 * 7)
    assert stats["total"] == 5
    assert stats["correct"] == 3
    assert stats["incorrect"] == 2
    assert stats["top_words"][0] == ("leverage", 5)
```

**Step 2: Run — expect fail**

```bash
pytest tests/test_storage.py -v
```

**Step 3: Add methods to `bot/storage.py`**

```python
    def save_checked_comment(
        self,
        *,
        comment_id: int,
        discussion_group_id: int,
        post_id: int,
        user_id: int,
        username: str | None,
        user_sentence: str,
        is_correct: bool,
        used_target_word: bool,
        corrected: str,
        explanation_uz: str,
        bot_reply_id: int | None,
        checked_at: int,
        ai_cost_usd: float,
    ) -> bool:
        """Returns True if inserted, False if duplicate."""
        cur = self._connect().execute(
            """INSERT OR IGNORE INTO checked_comments
               (comment_id, discussion_group_id, post_id, user_id, username,
                user_sentence, is_correct, used_target_word, corrected,
                explanation_uz, bot_reply_id, checked_at, ai_cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (comment_id, discussion_group_id, post_id, user_id, username,
             user_sentence, int(is_correct), int(used_target_word), corrected,
             explanation_uz, bot_reply_id, checked_at, ai_cost_usd),
        )
        return cur.rowcount > 0

    def was_comment_checked(self, comment_id: int) -> bool:
        row = self._connect().execute(
            "SELECT 1 FROM checked_comments WHERE comment_id=?", (comment_id,)
        ).fetchone()
        return row is not None

    def stats_since(self, since_ts: int) -> dict:
        conn = self._connect()
        total = conn.execute(
            "SELECT COUNT(*) FROM checked_comments WHERE checked_at>=?",
            (since_ts,),
        ).fetchone()[0]
        correct = conn.execute(
            "SELECT COUNT(*) FROM checked_comments WHERE checked_at>=? AND is_correct=1",
            (since_ts,),
        ).fetchone()[0]
        top_words = conn.execute(
            """SELECT p.word, COUNT(*) as cnt
               FROM checked_comments c JOIN posts p ON c.post_id = p.post_id
               WHERE c.checked_at>=?
               GROUP BY p.word ORDER BY cnt DESC LIMIT 3""",
            (since_ts,),
        ).fetchall()
        return {
            "total": total,
            "correct": correct,
            "incorrect": total - correct,
            "top_words": [(w, c) for w, c in top_words],
        }
```

**Step 4: Run — expect pass**

```bash
pytest tests/test_storage.py -v
```
Expected: 8 passed.

**Step 5: Commit**

```bash
git add bot/storage.py tests/test_storage.py
git commit -m "feat(storage): checked_comments CRUD, dedup, weekly stats"
```

---

### Task 9: post_parser module

**Files:**
- Create: `bot/post_parser.py`
- Create: `tests/test_post_parser.py`

**Step 1: Write failing test**

```python
# tests/test_post_parser.py
from bot.post_parser import extract_word


def test_extracts_simple_hashtag():
    text = "Today's word:\n\n#word_leverage\n\nMake sentences!"
    assert extract_word(text) == "leverage"


def test_case_insensitive():
    assert extract_word("#Word_Despite") == "despite"
    assert extract_word("#WORD_ACHIEVE") == "achieve"


def test_returns_none_when_no_hashtag():
    assert extract_word("Just a normal post with no marker.") is None
    assert extract_word("") is None


def test_ignores_hashtag_without_prefix():
    assert extract_word("#leverage") is None
    assert extract_word("#random") is None


def test_first_hashtag_wins():
    text = "#word_first some text #word_second"
    assert extract_word(text) == "first"


def test_only_latin_letters():
    assert extract_word("#word_leverage123") == "leverage"  # stops at non-letter
    assert extract_word("#word_") is None
```

**Step 2: Run — expect fail**

```bash
pytest tests/test_post_parser.py -v
```

**Step 3: Implement `bot/post_parser.py`**

```python
import re

_WORD_RE = re.compile(r"#word_([a-zA-Z]+)", re.IGNORECASE)


def extract_word(text: str | None) -> str | None:
    """Return the target word from a teacher's post, or None if no #word_X marker."""
    if not text:
        return None
    m = _WORD_RE.search(text)
    return m.group(1).lower() if m else None
```

**Step 4: Run — expect pass**

```bash
pytest tests/test_post_parser.py -v
```
Expected: 6 passed.

**Step 5: Commit**

```bash
git add bot/post_parser.py tests/test_post_parser.py
git commit -m "feat(parser): extract target word from #word_<word> hashtag"
```

---

### Task 10: ai_client — Pydantic schema

**Files:**
- Create: `bot/ai_client.py`
- Create: `tests/test_ai_client.py`

**Step 1: Write failing test**

```python
# tests/test_ai_client.py
from bot.ai_client import CheckResult


def test_check_result_schema():
    r = CheckResult(
        is_correct=False,
        used_target_word=True,
        corrected="I leverage my English skills.",
        explanation_uz="'leveraging' noto'g'ri — 'can' dan keyin infinitiv keladi.",
    )
    assert r.is_correct is False
    assert r.used_target_word is True
    assert r.corrected.startswith("I leverage")
    assert "noto'g'ri" in r.explanation_uz


def test_check_result_json_roundtrip():
    r = CheckResult(is_correct=True, used_target_word=True, corrected="x", explanation_uz="")
    data = r.model_dump()
    r2 = CheckResult(**data)
    assert r2 == r
```

**Step 2: Run — expect fail**

**Step 3: Implement schema in `bot/ai_client.py`**

```python
from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    is_correct: bool = Field(description="True if the sentence has no grammar/word-usage errors")
    used_target_word: bool = Field(description="True if the target word appears in the sentence and is used in the correct meaning")
    corrected: str = Field(description="The corrected English sentence. If no errors, return the original.")
    explanation_uz: str = Field(description="Explanation of the error in Uzbek (2-3 sentences). Empty string if no errors.")
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/ai_client.py tests/test_ai_client.py
git commit -m "feat(ai): CheckResult Pydantic schema for structured output"
```

---

### Task 11: ai_client — check_sentence with mocked API

**Files:**
- Modify: `bot/ai_client.py`
- Modify: `tests/test_ai_client.py`

**Step 1: Write failing test**

```python
# append to tests/test_ai_client.py
from unittest.mock import MagicMock, patch
import pytest
from bot.ai_client import GeminiClient


@pytest.mark.asyncio
async def test_check_sentence_calls_gemini_with_right_params():
    fake_result = CheckResult(
        is_correct=True, used_target_word=True,
        corrected="I leverage my time.", explanation_uz="",
    )
    fake_response = MagicMock()
    fake_response.parsed = fake_result
    fake_response.usage_metadata.prompt_token_count = 350
    fake_response.usage_metadata.candidates_token_count = 20

    with patch("bot.ai_client.genai.Client") as MockClient:
        instance = MockClient.return_value
        instance.aio.models.generate_content.return_value = fake_response

        client = GeminiClient(api_key="fake")
        result, cost = await client.check_sentence("leverage", "I leverage my time.")

        assert result.is_correct is True
        assert cost > 0

        call_kwargs = instance.aio.models.generate_content.call_args.kwargs
        assert "leverage" in str(call_kwargs["contents"])
```

**Step 2: Run — expect fail**

**Step 3: Implement in `bot/ai_client.py`**

```python
import asyncio
import logging
from google import genai
from google.genai import types

log = logging.getLogger(__name__)

MODEL = "gemini-3-1-flash-lite"

# Pricing per 1M tokens (Gemini 3.1 Flash Lite, April 2026)
PRICE_INPUT_PER_1M = 0.25
PRICE_OUTPUT_PER_1M = 1.50

SYSTEM_PROMPT = """Siz ingliz tilini o'rgatuvchi AI yordamchisiz. Sizning vazifangiz — \
talabaning ingliz tilidagi gapini tekshirish va jo'natuvchiga mehribon, \
rag'batlantiruvchi fikr bildirish.

TEKSHIRUV MEZONLARI:
1. Grammatika (zamonlar, artikl, gap tuzilishi)
2. Maqsadli so'z TO'G'RI ma'noda ishlatilganmi

JAVOB FORMATI — faqat JSON (is_correct, used_target_word, corrected, explanation_uz).

QOIDALAR:
- Mehribon ohang. Hech qachon "siz xato qildingiz" demang.
- Tushuntirish 2-3 jumladan oshmasin.
- Maqsadli so'z yo'q bo'lsa → is_correct=false, eslatib qo'ying.
- Grammatik to'g'ri, lekin so'z noto'g'ri ma'noda → is_correct=false.
- explanation_uz faqat O'ZBEK tilida, xato bo'lmasa — bo'sh string.
"""


class GeminiClient:
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    async def check_sentence(self, word: str, sentence: str) -> tuple[CheckResult, float]:
        user_msg = f"Maqsadli so'z: {word}\nTalaba gapi: {sentence}"

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.aio.models.generate_content(
                    model=MODEL,
                    contents=user_msg,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=400,
                        response_mime_type="application/json",
                        response_schema=CheckResult,
                    ),
                )
                cost = self._calc_cost(resp.usage_metadata)
                return resp.parsed, cost
            except Exception as e:
                last_err = e
                log.warning("Gemini attempt %d failed: %s", attempt + 1, e)
                await asyncio.sleep(2 ** (attempt + 1))

        raise RuntimeError(f"Gemini failed after 3 attempts: {last_err}")

    @staticmethod
    def _calc_cost(usage) -> float:
        inp = (usage.prompt_token_count / 1_000_000) * PRICE_INPUT_PER_1M
        out = (usage.candidates_token_count / 1_000_000) * PRICE_OUTPUT_PER_1M
        return round(inp + out, 6)
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/ai_client.py tests/test_ai_client.py
git commit -m "feat(ai): check_sentence with Gemini 3.1 Flash Lite + retry + cost tracking"
```

---

### Task 12: ai_client — integration test (opt-in)

**Files:**
- Modify: `tests/test_ai_client.py`

**Step 1: Add integration test**

```python
import os

@pytest.mark.integration
@pytest.mark.asyncio
async def test_gemini_real_call_uzbek_explanation():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")

    client = GeminiClient(api_key=key)
    result, cost = await client.check_sentence("leverage", "I am leveraging the box.")

    # Wrong meaning of "leverage" (lifting is wrong)
    assert result.is_correct is False
    assert result.used_target_word is True  # present, but wrong meaning
    assert len(result.explanation_uz) > 10
    # Uzbek check — common Uzbek letters
    assert any(c in result.explanation_uz for c in "o'gchshnq")
    assert cost > 0
```

**Step 2: Run (if you have a key)**

```bash
pytest tests/test_ai_client.py -m integration -v
```

If skipped — fine. Run real test when `GEMINI_API_KEY` is in `.env`.

**Step 3: Commit**

```bash
git add tests/test_ai_client.py
git commit -m "test(ai): add opt-in integration test for real Gemini call"
```

---

### Task 13: reply_sender — templates

**Files:**
- Create: `bot/reply_sender.py`
- Create: `tests/test_reply_sender.py`

**Step 1: Write failing test**

```python
# tests/test_reply_sender.py
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
    assert "ishlat" in text.lower()  # Uzbek "use"
```

**Step 2: Run — expect fail**

**Step 3: Implement `bot/reply_sender.py`**

```python
from bot.ai_client import CheckResult


CORRECT_TEMPLATE = "✅ Zo'r! To'g'ri gap tuzibsiz. 👏"

ERROR_TEMPLATE = (
    "📝 Yaxshi urinish!\n\n"
    "✅ To'g'ri varianti: \"{corrected}\"\n\n"
    "💡 Tushuntirish: {explanation_uz}"
)


def format_reply(result: CheckResult) -> str:
    if result.is_correct:
        return CORRECT_TEMPLATE
    return ERROR_TEMPLATE.format(
        corrected=result.corrected,
        explanation_uz=result.explanation_uz,
    )
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/reply_sender.py tests/test_reply_sender.py
git commit -m "feat(reply): format_reply with correct/error templates"
```

---

### Task 14: comment_checker — language heuristic

**Files:**
- Create: `bot/comment_checker.py`
- Create: `tests/test_comment_checker.py`

**Step 1: Write failing test**

```python
# tests/test_comment_checker.py
from bot.comment_checker import is_probably_english


def test_english_sentence_detected():
    assert is_probably_english("I can leverage my time to study.") is True


def test_uzbek_ignored():
    assert is_probably_english("Men leverage so'zini bilaman") is False


def test_russian_ignored():
    assert is_probably_english("Я использую leverage каждый день") is False


def test_mixed_below_threshold():
    # mostly cyrillic
    assert is_probably_english("bu leverage so'zi uchun misol") is False


def test_empty_string():
    assert is_probably_english("") is False
```

**Step 2: Run — expect fail**

**Step 3: Implement language check**

```python
# bot/comment_checker.py
def is_probably_english(text: str) -> bool:
    """Simple heuristic: >=70% of letters are ASCII latin → treat as English."""
    if not text:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if "a" <= c.lower() <= "z")
    return (latin / len(letters)) >= 0.70
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/comment_checker.py tests/test_comment_checker.py
git commit -m "feat(checker): is_probably_english heuristic (>=70% latin letters)"
```

---

### Task 15: comment_checker — orchestration

**Files:**
- Modify: `bot/comment_checker.py`
- Modify: `tests/test_comment_checker.py`

**Step 1: Write failing test**

```python
# append to tests/test_comment_checker.py
import tempfile, os, time
from unittest.mock import AsyncMock, MagicMock
import pytest
from bot.ai_client import CheckResult
from bot.comment_checker import CommentChecker
from bot.storage import Storage


@pytest.fixture
def checker_env():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    storage = Storage(path)
    storage.init_db()
    storage.save_post(100, -100111, "leverage", int(time.time()))

    ai = MagicMock()
    ai.check_sentence = AsyncMock(return_value=(
        CheckResult(is_correct=True, used_target_word=True,
                    corrected="I leverage my time.", explanation_uz=""),
        0.0003,
    ))

    sender = AsyncMock(return_value=9999)  # returns bot_reply_id

    checker = CommentChecker(storage=storage, ai_client=ai, send_reply=sender)

    yield {"checker": checker, "storage": storage, "ai": ai, "sender": sender}

    storage.close()
    os.unlink(path)


@pytest.mark.asyncio
async def test_skips_when_no_word_for_post(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=1, discussion_group_id=-100222,
        reply_to_post_id=999,  # unknown post
        user_id=1, username="a", text="I leverage time.",
    )
    checker_env["ai"].check_sentence.assert_not_called()


@pytest.mark.asyncio
async def test_skips_non_english(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=2, discussion_group_id=-100222,
        reply_to_post_id=100,
        user_id=1, username="a", text="Men leverage so'zini bilaman",
    )
    checker_env["ai"].check_sentence.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_calls_ai_and_sends_reply(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=3, discussion_group_id=-100222,
        reply_to_post_id=100,
        user_id=1, username="alice", text="I leverage my time.",
    )
    checker_env["ai"].check_sentence.assert_awaited_once_with("leverage", "I leverage my time.")
    checker_env["sender"].assert_awaited_once()
    assert checker_env["storage"].was_comment_checked(3)


@pytest.mark.asyncio
async def test_dedup_does_not_recheck(checker_env):
    c = checker_env["checker"]
    await c.check(
        comment_id=4, discussion_group_id=-100222, reply_to_post_id=100,
        user_id=1, username="a", text="I leverage time.",
    )
    await c.check(
        comment_id=4, discussion_group_id=-100222, reply_to_post_id=100,
        user_id=1, username="a", text="I leverage time.",
    )
    assert checker_env["ai"].check_sentence.await_count == 1
```

**Step 2: Run — expect fail**

**Step 3: Implement `CommentChecker` class**

```python
# bot/comment_checker.py (append to existing module)
import logging
import time
from typing import Awaitable, Callable

from bot.ai_client import GeminiClient, CheckResult
from bot.reply_sender import format_reply
from bot.storage import Storage

log = logging.getLogger(__name__)

# type: (chat_id, reply_to_message_id, text) -> bot_message_id
SendReplyFn = Callable[[int, int, str], Awaitable[int | None]]


class CommentChecker:
    def __init__(self, storage: Storage, ai_client: GeminiClient, send_reply: SendReplyFn):
        self._storage = storage
        self._ai = ai_client
        self._send = send_reply

    async def check(
        self, *, comment_id: int, discussion_group_id: int,
        reply_to_post_id: int, user_id: int, username: str | None, text: str,
    ) -> None:
        # 1. Dedupe
        if self._storage.was_comment_checked(comment_id):
            return

        # 2. Resolve word
        word = self._storage.get_word_for_post(reply_to_post_id)
        if not word:
            return

        # 3. Language check
        if not is_probably_english(text):
            log.info("Skipping non-English comment %d", comment_id)
            return

        # 4. Ask AI
        try:
            result, cost = await self._ai.check_sentence(word, text)
        except Exception as e:
            log.warning("AI failed for comment %d: %s", comment_id, e)
            return

        # 5. Send reply
        reply_text = format_reply(result)
        bot_reply_id = None
        try:
            bot_reply_id = await self._send(discussion_group_id, comment_id, reply_text)
        except Exception as e:
            log.warning("Failed to send reply for comment %d: %s", comment_id, e)

        # 6. Persist
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
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/comment_checker.py tests/test_comment_checker.py
git commit -m "feat(checker): orchestrate dedup, lang-check, AI call, reply, persist"
```

---

### Task 16: reporter — weekly summary generation

**Files:**
- Create: `bot/reporter.py`
- Create: `tests/test_reporter.py`

**Step 1: Write failing test**

```python
# tests/test_reporter.py
import tempfile, os, time
import pytest
from bot.storage import Storage
from bot.reporter import build_weekly_report


@pytest.fixture
def populated_storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = Storage(path)
    s.init_db()

    now = int(time.time())
    s.save_post(1, -100111, "leverage", now - 86400 * 2)
    s.save_post(2, -100111, "despite", now - 86400 * 4)
    for i in range(10):
        s.save_checked_comment(
            comment_id=100 + i, discussion_group_id=-100222, post_id=1,
            user_id=1, username="u", user_sentence="s",
            is_correct=(i < 6), used_target_word=True, corrected="s",
            explanation_uz="", bot_reply_id=None,
            checked_at=now - i * 3600, ai_cost_usd=0.0003,
        )
    for i in range(5):
        s.save_checked_comment(
            comment_id=200 + i, discussion_group_id=-100222, post_id=2,
            user_id=2, username="v", user_sentence="s",
            is_correct=True, used_target_word=True, corrected="s",
            explanation_uz="", bot_reply_id=None,
            checked_at=now - i * 3600, ai_cost_usd=0.0003,
        )

    yield s
    s.close()
    os.unlink(path)


def test_report_includes_totals_and_top_words(populated_storage):
    report = build_weekly_report(populated_storage)

    assert "15" in report            # total
    assert "leverage" in report      # top word
    assert "despite" in report
    assert "%" in report             # percentages
```

**Step 2: Run — expect fail**

**Step 3: Implement `bot/reporter.py`**

```python
import time
from bot.storage import Storage


def build_weekly_report(storage: Storage, now_ts: int | None = None) -> str:
    now = now_ts if now_ts is not None else int(time.time())
    since = now - 86400 * 7
    s = storage.stats_since(since)

    if s["total"] == 0:
        return "📊 Haftalik hisobot\n\nO'tgan hafta tekshirilgan gaplar yo'q."

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
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/reporter.py tests/test_reporter.py
git commit -m "feat(reporter): build_weekly_report with totals, correct%, top words"
```

---

## Phase 3 — Wiring (aiogram handlers + main)

### Task 17: handlers — channel post handler

**Files:**
- Create: `bot/handlers.py`
- Create: `tests/test_handlers.py`

**Step 1: Write failing test**

```python
# tests/test_handlers.py
import tempfile, os, time
from unittest.mock import MagicMock, AsyncMock
import pytest
from bot.handlers import handle_channel_post
from bot.storage import Storage


@pytest.fixture
def storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = Storage(path)
    s.init_db()
    yield s
    s.close()
    os.unlink(path)


@pytest.mark.asyncio
async def test_channel_post_with_hashtag_saves_word(storage):
    msg = MagicMock()
    msg.message_id = 42
    msg.chat.id = -100111
    msg.text = "Word of the day #word_leverage"
    msg.caption = None
    msg.date.timestamp.return_value = 1000.0

    await handle_channel_post(msg, storage)

    assert storage.get_word_for_post(42) == "leverage"


@pytest.mark.asyncio
async def test_channel_post_without_hashtag_ignored(storage):
    msg = MagicMock()
    msg.message_id = 43
    msg.chat.id = -100111
    msg.text = "Just a regular post"
    msg.caption = None
    msg.date.timestamp.return_value = 1000.0

    await handle_channel_post(msg, storage)

    assert storage.get_word_for_post(43) is None
```

**Step 2: Run — expect fail**

**Step 3: Implement `handle_channel_post` in `bot/handlers.py`**

```python
# bot/handlers.py
import logging
from aiogram.types import Message
from bot.post_parser import extract_word
from bot.storage import Storage

log = logging.getLogger(__name__)


async def handle_channel_post(msg: Message, storage: Storage) -> None:
    text = msg.text or msg.caption or ""
    word = extract_word(text)
    if not word:
        return
    storage.save_post(
        post_id=msg.message_id,
        channel_id=msg.chat.id,
        word=word,
        posted_at=int(msg.date.timestamp()),
    )
    log.info("Saved word '%s' for post %d", word, msg.message_id)
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/handlers.py tests/test_handlers.py
git commit -m "feat(handlers): channel post handler extracts and saves target word"
```

---

### Task 18: handlers — discussion message handler

**Files:**
- Modify: `bot/handlers.py`
- Modify: `tests/test_handlers.py`

**Step 1: Write failing test**

```python
# append to tests/test_handlers.py
from unittest.mock import AsyncMock
from bot.handlers import handle_discussion_message


@pytest.mark.asyncio
async def test_discussion_message_resolves_post_and_calls_checker(storage):
    storage.save_post(77, -100111, "achieve", int(time.time()))

    checker = AsyncMock()

    msg = MagicMock()
    msg.message_id = 500
    msg.chat.id = -100222
    msg.from_user.id = 999
    msg.from_user.username = "student1"
    msg.text = "I achieve my goals."
    msg.reply_to_message.forward_from_message_id = 77

    await handle_discussion_message(msg, checker)

    checker.check.assert_awaited_once()
    kwargs = checker.check.await_args.kwargs
    assert kwargs["comment_id"] == 500
    assert kwargs["reply_to_post_id"] == 77
    assert kwargs["text"] == "I achieve my goals."


@pytest.mark.asyncio
async def test_discussion_message_without_reply_chain_ignored(storage):
    checker = AsyncMock()
    msg = MagicMock()
    msg.reply_to_message = None
    msg.text = "random comment"

    await handle_discussion_message(msg, checker)

    checker.check.assert_not_called()
```

**Step 2: Run — expect fail**

**Step 3: Implement `handle_discussion_message`**

```python
# append to bot/handlers.py
from bot.comment_checker import CommentChecker


async def handle_discussion_message(msg: Message, checker: CommentChecker) -> None:
    if not msg.text:
        return
    if not msg.reply_to_message:
        return
    channel_post_id = msg.reply_to_message.forward_from_message_id
    if not channel_post_id:
        return

    await checker.check(
        comment_id=msg.message_id,
        discussion_group_id=msg.chat.id,
        reply_to_post_id=channel_post_id,
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        text=msg.text,
    )
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/handlers.py tests/test_handlers.py
git commit -m "feat(handlers): discussion message handler resolves post via forward chain"
```

---

### Task 19: handlers — /stats command for teacher

**Files:**
- Modify: `bot/handlers.py`
- Modify: `tests/test_handlers.py`

**Step 1: Write failing test**

```python
# append to tests/test_handlers.py
from bot.handlers import handle_stats_command


@pytest.mark.asyncio
async def test_stats_command_sends_report_to_teacher(storage):
    msg = MagicMock()
    msg.from_user.id = 42
    msg.answer = AsyncMock()

    await handle_stats_command(msg, storage, teacher_id=42)

    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "Haftalik hisobot" in text


@pytest.mark.asyncio
async def test_stats_command_ignored_for_non_teacher(storage):
    msg = MagicMock()
    msg.from_user.id = 99
    msg.answer = AsyncMock()

    await handle_stats_command(msg, storage, teacher_id=42)
    msg.answer.assert_not_called()
```

**Step 2: Run — expect fail**

**Step 3: Implement**

```python
# append to bot/handlers.py
from bot.reporter import build_weekly_report


async def handle_stats_command(msg: Message, storage: Storage, teacher_id: int) -> None:
    if msg.from_user.id != teacher_id:
        return
    report = build_weekly_report(storage)
    await msg.answer(report)
```

**Step 4: Run — expect pass**

**Step 5: Commit**

```bash
git add bot/handlers.py tests/test_handlers.py
git commit -m "feat(handlers): /stats command returns weekly report to teacher"
```

---

### Task 20: main.py — entry point wiring everything

**Files:**
- Create: `bot/main.py`

**Step 1: Implement main**

```python
# bot/main.py
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

    ai_client = GeminiClient(api_key=cfg.gemini_api_key)
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

    # Weekly report — Sunday 20:00 Tashkent time
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
```

**Step 2: Smoke-run (will fail without real `.env`, that's OK)**

```bash
python -m bot.main
```
Expected: `RuntimeError: Missing required env var: TG_BOT_TOKEN` — proves config wiring works.

**Step 3: Run the full test suite**

```bash
pytest -v
```
Expected: all tests (~25+) pass.

**Step 4: Commit**

```bash
git add bot/main.py
git commit -m "feat(main): wire config, storage, AI, handlers, scheduler into entrypoint"
```

---

## Phase 4 — Deployment

### Task 21: systemd service file

**Files:**
- Create: `systemd/teachereng.service`

**Step 1: Write unit file**

```ini
[Unit]
Description=teachereng Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/teachereng
EnvironmentFile=/opt/teachereng/.env
ExecStart=/opt/teachereng/.venv/bin/python -m bot.main
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Step 2: Commit**

```bash
git add systemd/teachereng.service
git commit -m "chore(deploy): systemd unit file for bot process"
```

---

### Task 22: DEPLOY.md with full server setup

**Files:**
- Create: `DEPLOY.md`

**Step 1: Write deployment guide**

````markdown
# Deployment to dev server

Server: `164.92.199.126` (root user)

## First-time setup

```bash
ssh root@164.92.199.126

apt update && apt install -y python3.11 python3.11-venv python3-pip git

cd /opt
git clone https://github.com/Ibrakhimzhanov/teachereng.git
cd teachereng

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
nano .env
# Fill in: TG_BOT_TOKEN, GEMINI_API_KEY, CHANNEL_ID, DISCUSSION_GROUP_ID, TEACHER_TG_ID

cp systemd/teachereng.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now teachereng

journalctl -u teachereng -f
```

## Updates

```bash
# Locally
git push origin main

# On server
ssh root@164.92.199.126 "cd /opt/teachereng && git pull && systemctl restart teachereng"
```

## Check status

```bash
systemctl status teachereng
journalctl -u teachereng -f
sqlite3 /opt/teachereng/data.db 'SELECT COUNT(*) FROM checked_comments'
```

## Telegram setup (one-time)

1. Create bot via [@BotFather](https://t.me/BotFather), save token.
2. Disable privacy: `/setprivacy` → select bot → `Disable` (so bot sees all group messages).
3. Add bot as **admin** in:
   - The channel (to receive channel_posts)
   - The **discussion group** linked to the channel (to read comments and reply).
4. Get `CHANNEL_ID` and `DISCUSSION_GROUP_ID`: forward one message from each to [@userinfobot](https://t.me/userinfobot), or use `getUpdates` API.
5. Get `TEACHER_TG_ID` — teacher messages [@userinfobot](https://t.me/userinfobot).

## Acceptance test

1. Teacher posts `Word of the day\n\n#word_leverage\n\nMake sentences!` → check `sqlite3 data.db "SELECT * FROM posts"` — row appears.
2. Student writes `I leverage my time.` in comments → bot replies `✅ Zo'r!`.
3. Student writes `I am leveraging the box.` (wrong meaning) → bot replies with correction + Uzbek explanation.
4. Student writes `I like apples.` (no target word) → bot reminds to use the word.
5. Student writes `Men leverage ishlataman` (Uzbek) → no reply.
6. Sunday 20:00 Tashkent → teacher receives weekly report in DM.
````

**Step 2: Commit**

```bash
git add DEPLOY.md
git commit -m "docs: add full deployment guide for dev server"
```

---

### Task 23: Push everything to GitHub

**Files:** none (git operation only)

**Step 1: Verify clean state + all tests pass**

```bash
pytest -v
git status
```
Expected: all tests pass, working tree clean.

**Step 2: Push**

```bash
git push -u origin main
```

**Step 3: Verify on GitHub**

Open [https://github.com/Ibrakhimzhanov/teachereng](https://github.com/Ibrakhimzhanov/teachereng) — all files visible, commits in order.

---

## Phase 5 — Server deployment (manual, not part of this plan)

The user (with tokens in hand) should follow `DEPLOY.md` on `164.92.199.126`. This is out of scope for this plan because it requires interactive `.env` editing + Telegram admin setup.

---

## Definition of Done

- [ ] All 23 tasks committed in order
- [ ] `pytest -v` — all unit tests pass
- [ ] `python -m bot.main` fails with clear "Missing env" error (proof of fail-fast)
- [ ] Repository pushed to GitHub
- [ ] `DEPLOY.md` readable and complete
- [ ] No secrets in git history
- [ ] Optional: `pytest -m integration` passes against real Gemini API

## Out-of-scope reminders (from design doc)

These are explicit NO's for v1 — don't add them in follow-up "cleanup" tasks:
- Webhook mode (stay with polling)
- Rate-limiting users
- Toxicity detection
- Multi-channel support
- Web admin dashboard
- `🚩 Report` button (table exists, feature later)
