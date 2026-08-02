"""
MCQ database layer — question_bank and fact_attempts tables.
Uses the same interview.db file, separate tables.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

_DB_PATH = Path(__file__).parent.parent / "interview.db"


class McqDB:
    """CRUD for MCQ questions and attempt logging."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._path = str(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS question_bank (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic       TEXT NOT NULL,
                    difficulty  TEXT NOT NULL CHECK(difficulty IN ('easy','medium','hard')),
                    question    TEXT NOT NULL,
                    options     TEXT NOT NULL,
                    correct_answer TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fact_attempts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       TEXT NOT NULL,
                    session_id    TEXT NOT NULL,
                    question_id   INTEGER NOT NULL,
                    chosen_answer TEXT,
                    correct       INTEGER NOT NULL,
                    time_taken_ms INTEGER NOT NULL,
                    attempted_at  TEXT NOT NULL,
                    FOREIGN KEY (question_id) REFERENCES question_bank(question_id)
                );
            """)

    # --- Questions ---

    def get_questions_by_topic(self, topic: str | None = None,
                              limit: int = 10) -> list[dict]:
        """Fetch questions. If topic is None, mix across all topics."""
        with self._connect() as conn:
            if topic:
                rows = conn.execute(
                    "SELECT * FROM question_bank WHERE topic = ? ORDER BY RANDOM() LIMIT ?",
                    (topic, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM question_bank ORDER BY RANDOM() LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_question_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM question_bank").fetchone()
            return row[0]

    # --- Attempts ---

    def log_attempt(self, user_id: str, session_id: str, question_id: int,
                    chosen_answer: str | None, correct: bool, time_taken_ms: int):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO fact_attempts
                   (user_id, session_id, question_id, chosen_answer, correct, time_taken_ms, attempted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, session_id, question_id, chosen_answer,
                 int(correct), time_taken_ms, now),
            )

    def get_user_attempts(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fact_attempts WHERE user_id = ? ORDER BY attempted_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
