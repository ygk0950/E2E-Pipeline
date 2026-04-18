"""Tests for the FastAPI application."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.api.main import app


@pytest.fixture(autouse=True)
def init_test_db(tmp_path, monkeypatch):
    """Point the DB to a temp file for each test."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_file)
    # Re-import to pick up the patched env var
    import app.db.database as db_mod
    db_mod.DB_PATH = db_file
    db_mod.init_db()


@pytest.mark.asyncio
async def test_health_check() -> None:
    """GET / should return 200 and {"status": "ok"}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_pipelines() -> None:
    """GET /pipelines should return a list containing 'weather' and 'crypto'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/pipelines")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert "weather" in names
    assert "crypto" in names


@pytest.mark.asyncio
async def test_trigger_pipeline() -> None:
    """POST /pipelines/weather/trigger should return 202."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/pipelines/weather/trigger")
    assert response.status_code == 202
    data = response.json()
    assert "message" in data
