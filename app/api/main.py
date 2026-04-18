"""FastAPI application — exposes pipeline management endpoints."""

import logging
import os
from typing import List

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.db import queries
from app.db.database import init_db
from app.pipeline.registry import PIPELINE_REGISTRY
from app.api import runner
from app.api.models import PipelineInfo, RunResult, TriggerResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ETL Pipeline API", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    """Initialise the SQLite database on startup."""
    init_db()
    logger.info("ETL Pipeline API started")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/", tags=["health"])
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/pipelines", response_model=List[PipelineInfo], tags=["pipelines"])
def list_pipelines() -> List[PipelineInfo]:
    """List all registered pipelines with their latest run information."""
    last_runs = {row["pipeline"]: row for row in queries.get_all_pipelines_last_run()}
    result = []
    for name in PIPELINE_REGISTRY:
        run = last_runs.get(name)
        result.append(
            PipelineInfo(
                name=name,
                last_run_at=run["started_at"] if run else None,
                last_status=run["status"] if run else None,
                last_rows_loaded=run["rows_loaded"] if run else None,
            )
        )
    return result


@app.post(
    "/pipelines/{name}/trigger",
    response_model=TriggerResponse,
    status_code=202,
    tags=["pipelines"],
)
def trigger_pipeline(name: str) -> TriggerResponse:
    """Trigger a pipeline run in the background."""
    if name not in PIPELINE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    success = runner.trigger(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    return TriggerResponse(message=f"Pipeline '{name}' triggered successfully")


@app.get("/pipelines/{name}/status", tags=["pipelines"])
def get_pipeline_status(name: str) -> dict:
    """Get the current in-memory status of a pipeline."""
    if name not in PIPELINE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    status = runner.get_status(name)
    last_run = queries.get_last_run(name)
    return {
        "pipeline": name,
        "current_status": status or (dict(last_run)["status"] if last_run else "never_run"),
    }


@app.get("/pipelines/{name}/runs", response_model=List[RunResult], tags=["pipelines"])
def get_pipeline_runs(name: str) -> List[RunResult]:
    """Return the last 20 runs for a pipeline."""
    if name not in PIPELINE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    runs = queries.get_runs(name, limit=20)
    return [RunResult(**r) for r in runs]


@app.delete("/s3/clear", tags=["s3"])
def clear_s3_bucket() -> dict:
    """Delete all objects in the S3 bucket."""
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="S3_BUCKET not configured")

    s3 = boto3.client("s3")
    try:
        paginator = s3.get_paginator("list_objects_v2")
        deleted = 0
        for page in paginator.paginate(Bucket=bucket):
            objects = page.get("Contents", [])
            if objects:
                s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                )
                deleted += len(objects)
        logger.info("Cleared S3 bucket %s — deleted %d objects", bucket, deleted)
        return {"message": f"Deleted {deleted} objects from s3://{bucket}"}
    except ClientError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/pipelines/{name}/logs", tags=["pipelines"])
def get_pipeline_logs(name: str) -> dict:
    """Return logs captured from the last run of a pipeline."""
    if name not in PIPELINE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found")

    logs = runner.get_logs(name)
    return {"pipeline": name, "logs": logs}
