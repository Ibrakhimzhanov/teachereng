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
