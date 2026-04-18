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
        parent = Path(self.db_path).parent
        if str(parent) and str(parent) != ".":
            parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.execute("PRAGMA journal_mode=WAL")
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
