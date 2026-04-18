"""SQLite database setup for the ETL pipeline project."""

import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/etl_runs.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline    TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    rows_loaded INTEGER,
    error_msg   TEXT,
    s3_key      TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set to Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the pipeline_runs table if it does not exist."""
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    logger.info("Database initialised at %s", DB_PATH)
