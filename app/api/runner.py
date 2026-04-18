"""Background runner that executes pipelines in separate threads and tracks status."""

import logging
import threading
from typing import Optional

from app.pipeline.registry import PIPELINE_REGISTRY

logger = logging.getLogger(__name__)

# In-memory status store: pipeline_name → {"status": ..., "run_id": ..., "logs": [...]}
_status: dict = {}
_logs: dict = {}
_lock = threading.Lock()


def _run_pipeline(name: str) -> None:
    """Target function for the background thread."""
    pipeline_cls = PIPELINE_REGISTRY.get(name)
    if pipeline_cls is None:
        logger.error("Unknown pipeline: %s", name)
        return

    pipeline = pipeline_cls()

    with _lock:
        _status[name] = "running"
        _logs[name] = []

    # Capture logs for this run
    log_handler = _ListHandler(_logs[name])
    log_handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)

    try:
        result = pipeline.run()
        with _lock:
            _status[name] = result["status"]
    except Exception as exc:  # noqa: BLE001
        with _lock:
            _status[name] = "failed"
        logger.exception("Unhandled error in pipeline %s: %s", name, exc)
    finally:
        root_logger.removeHandler(log_handler)


def trigger(name: str) -> bool:
    """
    Trigger a pipeline run in a background thread.

    Returns False if the pipeline is unknown, True otherwise.
    """
    if name not in PIPELINE_REGISTRY:
        return False

    with _lock:
        if _status.get(name) == "running":
            logger.info("Pipeline '%s' is already running — skipping trigger", name)
            return True

    t = threading.Thread(target=_run_pipeline, args=(name,), daemon=True)
    t.start()
    logger.info("Triggered pipeline '%s' in background thread", name)
    return True


def get_status(name: str) -> Optional[str]:
    """Return the current in-memory status of a pipeline, or None if never run."""
    with _lock:
        return _status.get(name)


def get_logs(name: str) -> list:
    """Return log lines captured from the last run of a pipeline."""
    with _lock:
        return list(_logs.get(name, []))


class _ListHandler(logging.Handler):
    """A logging handler that appends formatted records to a list."""

    def __init__(self, target: list) -> None:
        super().__init__()
        self._target = target
        fmt = "[%(asctime)s] %(levelname)s %(name)s — %(message)s"
        self.setFormatter(logging.Formatter(fmt))

    def emit(self, record: logging.LogRecord) -> None:
        self._target.append(self.format(record))
