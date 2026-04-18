# ETL Pipeline Project — Claude Code Instructions

This document is the single source of truth for this project.
Read it fully before writing any code.

---

## What we are building

A production-style ELT pipeline with:
- Two data sources (weather + crypto prices) pulled via free public APIs
- FastAPI backend that triggers pipelines, returns status, and streams logs
- Streamlit UI to monitor pipelines, trigger runs, and view results
- Docker container that runs both services together
- GitHub Actions CI/CD that auto-deploys to an AWS EC2 instance on every push to main

---

## Tech stack

| Layer | Tool |
|---|---|
| Language | Python 3.11 |
| Extract | requests |
| Transform | pandas, pyarrow |
| Load | boto3 (S3) + SQLite (local results store) |
| API backend | FastAPI + uvicorn |
| UI | Streamlit |
| Container | Docker + docker-compose |
| CI/CD | GitHub Actions |
| Cloud storage | AWS S3 |
| Server | AWS EC2 t3.medium (Ubuntu 22.04) |

---

## Data sources

### Pipeline 1 — Weather (Open-Meteo)
- URL: `https://api.open-meteo.com/v1/forecast`
- No API key required
- Pulls hourly temperature, precipitation, windspeed for Delhi (lat=28.6139, lon=77.2090)
- Schedule: every 6 hours

### Pipeline 2 — Crypto prices (CoinGecko)
- URL: `https://api.coingecko.com/api/v3/coins/markets`
- No API key required for basic tier
- Pulls top 10 coins by market cap: price, volume, market cap, 24h change
- Schedule: every 1 hour

---

## Repo structure

```
etl-pipeline/
  app/
    pipeline/
      __init__.py
      base.py            # BasePipeline class all pipelines inherit from
      weather.py         # WeatherPipeline: extract → transform → load
      crypto.py          # CryptoPipeline: extract → transform → load
      registry.py        # Dict of all available pipelines by name
    api/
      __init__.py
      main.py            # FastAPI app
      models.py          # Pydantic models for requests/responses
      runner.py          # Runs pipelines in background threads, tracks status
    ui/
      streamlit_app.py   # Streamlit dashboard
    db/
      database.py        # SQLite setup: pipeline_runs table
      queries.py         # All DB read/write functions
  tests/
    test_weather.py
    test_crypto.py
    test_api.py
  .github/
    workflows/
      deploy.yml         # CI/CD: test → build → push to ECR → deploy to EC2
  Dockerfile
  docker-compose.yml
  requirements.txt
  .env.example
  CLAUDE.md              # this file
```

---

## Database schema (SQLite — file: `etl_runs.db`)

```sql
CREATE TABLE pipeline_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline    TEXT NOT NULL,          -- 'weather' or 'crypto'
  status      TEXT NOT NULL,          -- 'running', 'success', 'failed'
  started_at  TEXT NOT NULL,          -- ISO timestamp
  finished_at TEXT,                   -- ISO timestamp, null if still running
  rows_loaded INTEGER,                -- null if failed
  error_msg   TEXT,                   -- null if success
  s3_key      TEXT                    -- where data landed in S3
);
```

---

## BasePipeline class

Every pipeline inherits from this. It handles logging, status tracking, and the run lifecycle.

```python
# app/pipeline/base.py
class BasePipeline:
    name: str  # override in subclass

    def extract(self) -> dict:
        raise NotImplementedError

    def transform(self, raw: dict) -> pd.DataFrame:
        raise NotImplementedError

    def load(self, df: pd.DataFrame) -> str:
        # writes parquet to S3, returns s3_key
        raise NotImplementedError

    def run(self) -> dict:
        # orchestrates extract → transform → load
        # catches exceptions, records result to SQLite
        # returns {"status": "success"|"failed", "rows": int, "s3_key": str}
        pass
```

---

## FastAPI endpoints

```
GET  /                          # health check: {"status": "ok"}
GET  /pipelines                 # list all pipelines with last run status
POST /pipelines/{name}/trigger  # trigger a pipeline run (runs in background)
GET  /pipelines/{name}/status   # get current status of a pipeline
GET  /pipelines/{name}/runs     # get last 20 run history for a pipeline
GET  /pipelines/{name}/logs     # get logs from the last run
```

All responses use these Pydantic models:
- `PipelineInfo`: name, last_run_at, last_status, last_rows_loaded
- `RunResult`: id, pipeline, status, started_at, finished_at, rows_loaded, error_msg, s3_key
- `TriggerResponse`: message, run_id

---

## Streamlit UI pages

### Page 1 — Dashboard (default page)
- Header: "ETL Pipeline Monitor"
- Two cards side by side, one per pipeline
- Each card shows: pipeline name, last run status (green/red badge), last run time, rows loaded
- "Trigger Run" button on each card — calls POST /pipelines/{name}/trigger
- Auto-refreshes every 30 seconds using `st.rerun()`

### Page 2 — Run History
- Dropdown to select pipeline
- Table showing last 20 runs: started_at, status, rows_loaded, duration, s3_key
- Color rows red if status = failed

### Page 3 — Logs
- Dropdown to select pipeline
- Shows logs from last run in a scrollable code block
- "Trigger new run" button at top

Streamlit calls FastAPI via `http://localhost:8000` (both run in same container).

---

## Environment variables

Create a `.env` file (never commit this). Use `.env.example` as the template.

```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-south-1
S3_BUCKET=your-etl-bucket-name
FASTAPI_PORT=8000
STREAMLIT_PORT=8501
```

Load in Python using `python-dotenv`:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY .env .env

# Start both FastAPI and Streamlit using a shell script
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000 8501
CMD ["./start.sh"]
```

### start.sh
```bash
#!/bin/bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 &
streamlit run app/ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

---

## docker-compose.yml

```yaml
version: "3.9"
services:
  etl-app:
    build: .
    ports:
      - "8000:8000"
      - "8501:8501"
    env_file:
      - .env
    volumes:
      - ./etl_runs.db:/app/etl_runs.db
    restart: unless-stopped
```

---

## requirements.txt

```
fastapi==0.111.0
uvicorn==0.30.1
streamlit==1.35.0
pandas==2.2.2
pyarrow==16.1.0
boto3==1.34.131
requests==2.32.3
python-dotenv==1.0.1
pydantic==2.7.4
pytest==8.2.2
httpx==0.27.0
```

---

## GitHub Actions — .github/workflows/deploy.yml

The workflow does the following on every push to `main`:

1. Run tests (`pytest tests/`)
2. Build Docker image
3. Push image to AWS ECR (registry: `{AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/etl-pipeline`)
4. SSH into EC2 and run:
   ```bash
   docker pull {ECR_IMAGE_URL}
   docker stop etl-app || true
   docker rm etl-app || true
   docker run -d --name etl-app \
     -p 8000:8000 -p 8501:8501 \
     --env-file /home/ubuntu/.env \
     -v /home/ubuntu/etl_runs.db:/app/etl_runs.db \
     --restart unless-stopped \
     {ECR_IMAGE_URL}
   ```

### GitHub Secrets required (Settings → Secrets → Actions)
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_ACCOUNT_ID
EC2_HOST          # 3.108.95.185
EC2_SSH_KEY       # contents of etl-key.pem
```

---

## Tests

Write these tests in `tests/`:

### test_weather.py
- `test_extract_returns_dict` — mock requests, assert extract() returns a dict with 'hourly' key
- `test_transform_returns_dataframe` — pass mock raw data, assert DataFrame has correct columns
- `test_transform_row_count` — assert 24 rows (one per hour)

### test_crypto.py
- `test_extract_returns_list` — mock requests, assert extract() returns a list of 10 items
- `test_transform_returns_dataframe` — assert correct columns: coin_id, name, price_usd, market_cap, volume_24h, change_24h, ingested_at

### test_api.py
- `test_health_check` — GET / returns 200 and {"status": "ok"}
- `test_list_pipelines` — GET /pipelines returns list with 'weather' and 'crypto'
- `test_trigger_pipeline` — POST /pipelines/weather/trigger returns 202

Use `pytest` with `httpx.AsyncClient` for API tests.

---

## Code style rules

- All functions have type hints
- All modules have a docstring at the top
- No hardcoded values — everything from environment variables or config
- Logging using Python's `logging` module, not print statements
- Log format: `[%(asctime)s] %(levelname)s %(name)s — %(message)s`
- Every pipeline run logs: start, row count at each stage, S3 key, duration

---

## How to run locally (for development)

```bash
# 1. Clone the repo
git clone git@github.com:YOUR_USERNAME/etl-pipeline.git
cd etl-pipeline

# 2. Create .env from example
cp .env.example .env
# fill in your AWS credentials and bucket name

# 3. Run with docker-compose
docker-compose up --build

# 4. Open in browser
# Streamlit UI:  http://localhost:8501
# FastAPI docs:  http://localhost:8000/docs
```

---

## How to run on EC2 (production)

The GitHub Actions workflow handles deployment automatically on push to main.

To manually redeploy:
```bash
ssh -i etl-key.pem ubuntu@3.108.95.185
cd ~
docker pull {ECR_IMAGE_URL}
docker-compose up -d
```

---

## Order to build things (do not skip steps)

1. `app/db/database.py` and `app/db/queries.py` — set up SQLite first
2. `app/pipeline/base.py` — BasePipeline class
3. `app/pipeline/weather.py` — WeatherPipeline (extract, transform, load, run)
4. `app/pipeline/crypto.py` — CryptoPipeline (extract, transform, load, run)
5. `app/pipeline/registry.py` — pipeline registry dict
6. `app/api/models.py` — Pydantic models
7. `app/api/runner.py` — background runner and status tracker
8. `app/api/main.py` — FastAPI app with all endpoints
9. `app/ui/streamlit_app.py` — Streamlit UI (3 pages)
10. `tests/` — all test files
11. `Dockerfile` + `start.sh` + `docker-compose.yml`
12. `.github/workflows/deploy.yml`

---

## Definition of done

- `docker-compose up` starts both services with no errors
- Streamlit UI loads at localhost:8501
- Triggering a pipeline from the UI runs it and shows success/failure
- Run history page shows past runs
- All tests pass with `pytest`
- Pushing to main triggers GitHub Actions and deploys to EC2 automatically
