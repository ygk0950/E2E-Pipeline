"""All database read/write functions for pipeline_runs."""

import sqlite3
import logging
from typing import Optional
from .database import get_connection

logger = logging.getLogger(__name__)


def insert_run(pipeline: str, started_at: str) -> int:
    """Insert a new running record and return its id."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO pipeline_runs (pipeline, status, started_at)
            VALUES (?, 'running', ?)
            """,
            (pipeline, started_at),
        )
        conn.commit()
        run_id: int = cur.lastrowid
    logger.info("Inserted run id=%s for pipeline=%s", run_id, pipeline)
    return run_id


def update_run_success(run_id: int, finished_at: str, rows_loaded: int, s3_key: str) -> None:
    """Mark a run as successful."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET status='success', finished_at=?, rows_loaded=?, s3_key=?
            WHERE id=?
            """,
            (finished_at, rows_loaded, s3_key, run_id),
        )
        conn.commit()
    logger.info("Run id=%s marked success, rows=%s, s3_key=%s", run_id, rows_loaded, s3_key)


def update_run_failed(run_id: int, finished_at: str, error_msg: str) -> None:
    """Mark a run as failed."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET status='failed', finished_at=?, error_msg=?
            WHERE id=?
            """,
            (finished_at, error_msg, run_id),
        )
        conn.commit()
    logger.info("Run id=%s marked failed: %s", run_id, error_msg)


def get_last_run(pipeline: str) -> Optional[sqlite3.Row]:
    """Return the most recent run for a pipeline, or None."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM pipeline_runs
            WHERE pipeline=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (pipeline,),
        ).fetchone()
    return row


def get_runs(pipeline: str, limit: int = 20) -> list:
    """Return the last `limit` runs for a pipeline."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM pipeline_runs
            WHERE pipeline=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (pipeline, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_pipelines_last_run() -> list:
    """Return the latest run for every distinct pipeline."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.*
            FROM pipeline_runs p
            INNER JOIN (
                SELECT pipeline, MAX(id) AS max_id
                FROM pipeline_runs
                GROUP BY pipeline
            ) latest ON p.pipeline = latest.pipeline AND p.id = latest.max_id
            """
        ).fetchall()
    return [dict(r) for r in rows]
