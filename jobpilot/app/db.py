import json
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH, COMPANIES_FILE

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT DEFAULT '',
    remote INTEGER DEFAULT 0,
    url TEXT NOT NULL,
    description TEXT DEFAULT '',
    posted_at TEXT DEFAULT '',
    dedupe_hash TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'discovered',
    score INTEGER,
    score_reason TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS drafts (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
    cover_letter TEXT DEFAULT '',
    answers_json TEXT DEFAULT '[]',
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    resume_text TEXT DEFAULT '',
    resume_json TEXT DEFAULT '',
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS answers_bank (
    question TEXT PRIMARY KEY,
    answer TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS pipeline_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at TEXT DEFAULT (datetime('now')),
    summary TEXT
);
"""

DEFAULT_SETTINGS = {
    "title_keywords": "",        # comma-separated; empty = accept all titles
    "blocklist": "",             # comma-separated; hit in title/location = filtered
    "remote_only": "0",
    "strictness": "balanced",    # strict | balanced | loose
    "daily_cap": "20",
    "max_age_days": "30",
    "companies": "",             # JSON {source: [slugs]}, seeded from companies.json
}

DEFAULT_BANK_QUESTIONS = [
    "What is your notice period / earliest start date?",
    "What are your salary expectations?",
    "Are you legally authorized to work in the country of this job?",
    "Will you now or in the future require visa sponsorship?",
    "Are you willing to relocate?",
]

STRICTNESS_THRESHOLDS = {"strict": 80, "balanced": 65, "loose": 50}

# Statuses a job moves through. 'filtered' and 'skipped' are terminal ledger
# entries that keep dedupe permanent without cluttering the working views.
KANBAN_STATUSES = ["queued", "applied", "interviewing", "offer", "rejected"]


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript(SCHEMA)
        db.execute("INSERT OR IGNORE INTO profile (id) VALUES (1)")
        for q in DEFAULT_BANK_QUESTIONS:
            db.execute("INSERT OR IGNORE INTO answers_bank (question) VALUES (?)", (q,))
        for key, value in DEFAULT_SETTINGS.items():
            db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        row = db.execute("SELECT value FROM settings WHERE key='companies'").fetchone()
        if row and not row["value"] and COMPANIES_FILE.exists():
            db.execute(
                "UPDATE settings SET value=? WHERE key='companies'",
                (COMPANIES_FILE.read_text(),),
            )


def get_setting(db, key: str) -> str:
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else ""


def set_setting(db, key: str, value: str) -> None:
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_companies(db) -> dict:
    raw = get_setting(db, "companies")
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}
    return {src: data.get(src, []) for src in ("greenhouse", "lever", "ashby")}


def get_profile(db) -> sqlite3.Row:
    return db.execute("SELECT * FROM profile WHERE id=1").fetchone()


def get_answers_bank(db) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM answers_bank ORDER BY question").fetchall()


def set_job_status(db, job_id: int, status: str) -> None:
    db.execute(
        "UPDATE jobs SET status=?, updated_at=datetime('now') WHERE id=?",
        (status, job_id),
    )
