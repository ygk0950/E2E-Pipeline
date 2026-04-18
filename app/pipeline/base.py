"""Base pipeline class that all pipelines inherit from."""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.db import queries

logger = logging.getLogger(__name__)
LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s — %(message)s"


class BasePipeline:
    """Abstract base class providing the run lifecycle for all pipelines."""

    name: str = "base"

    def __init__(self) -> None:
        logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
        self._log = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Override these in subclasses
    # ------------------------------------------------------------------

    def extract(self) -> Any:
        """Fetch raw data from the source. Must be overridden."""
        raise NotImplementedError

    def transform(self, raw: Any) -> pd.DataFrame:
        """Transform raw data into a clean DataFrame. Must be overridden."""
        raise NotImplementedError

    def load(self, df: pd.DataFrame) -> str:
        """Write the DataFrame to S3 as Parquet and return the s3_key. Must be overridden."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """
        Orchestrate extract → transform → load.

        Returns a dict with keys: status, rows, s3_key.
        Catches all exceptions, persists the result to SQLite.
        """
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = queries.insert_run(self.name, started_at)
        self._log.info("Pipeline '%s' started — run_id=%s", self.name, run_id)

        try:
            self._log.info("Extracting …")
            raw = self.extract()

            self._log.info("Transforming …")
            df = self.transform(raw)
            self._log.info("Rows after transform: %d", len(df))

            self._log.info("Loading …")
            s3_key = self.load(df)
            rows_loaded = len(df)

            finished_at = datetime.now(timezone.utc).isoformat()
            queries.update_run_success(run_id, finished_at, rows_loaded, s3_key)

            duration = (
                datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
            ).total_seconds()
            self._log.info(
                "Pipeline '%s' succeeded — rows=%d  s3_key=%s  duration=%.1fs",
                self.name,
                rows_loaded,
                s3_key,
                duration,
            )
            return {"status": "success", "rows": rows_loaded, "s3_key": s3_key}

        except Exception as exc:  # noqa: BLE001
            finished_at = datetime.now(timezone.utc).isoformat()
            error_msg = str(exc)
            queries.update_run_failed(run_id, finished_at, error_msg)
            self._log.exception("Pipeline '%s' failed: %s", self.name, error_msg)
            return {"status": "failed", "rows": 0, "s3_key": ""}
