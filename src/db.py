import sqlite3
from typing import Generator

DATABASE_URL = "toneii.db"


def init_db():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            display_name TEXT NOT NULL,
            category TEXT NOT NULL,
            default_volume REAL DEFAULT 1.0
        )
        """
    )
    for statement in (
        "ALTER TABLE audio_files ADD COLUMN uploader_name TEXT DEFAULT 'Host'",
        "ALTER TABLE audio_files ADD COLUMN storage_type TEXT DEFAULT 'local'",
    ):
        try:
            cursor.execute(statement)
        except sqlite3.OperationalError:
            # SQLite reports a duplicate-column error if this migration already ran.
            pass
    conn.commit()
    conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
