"""Pydantic models for FastAPI requests and responses."""

from typing import Optional
from pydantic import BaseModel


class PipelineInfo(BaseModel):
    """Summary info for a pipeline."""

    name: str
    last_run_at: Optional[str] = None
    last_status: Optional[str] = None
    last_rows_loaded: Optional[int] = None


class RunResult(BaseModel):
    """Full details of a single pipeline run."""

    id: int
    pipeline: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    rows_loaded: Optional[int] = None
    error_msg: Optional[str] = None
    s3_key: Optional[str] = None


class TriggerResponse(BaseModel):
    """Response returned when a pipeline is triggered."""

    message: str
    run_id: Optional[int] = None
