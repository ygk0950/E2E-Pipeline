"""WeatherPipeline: extract → transform → load for Open-Meteo hourly data."""

import io
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
import pandas as pd
import requests

from .base import BasePipeline

logger = logging.getLogger(__name__)

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
LATITUDE = 28.6139   # Delhi
LONGITUDE = 77.2090


class WeatherPipeline(BasePipeline):
    """Pulls hourly weather data for Delhi from Open-Meteo and stores it in S3."""

    name = "weather"

    def extract(self) -> dict:
        """Fetch hourly forecast data from Open-Meteo. Returns the raw JSON dict."""
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "temperature_2m,precipitation,windspeed_10m",
            "forecast_days": 1,
            "timezone": "Asia/Kolkata",
        }
        response = requests.get(WEATHER_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data: dict = response.json()
        logger.info("Extracted weather data with %d hourly records", len(data.get("hourly", {}).get("time", [])))
        return data

    def transform(self, raw: dict) -> pd.DataFrame:
        """
        Transform the raw Open-Meteo JSON into a flat DataFrame.

        Columns: time, temperature_2m, precipitation, windspeed_10m, ingested_at
        Guarantees exactly 24 rows (one per hour).
        """
        hourly = raw["hourly"]
        df = pd.DataFrame({
            "time": hourly["time"],
            "temperature_2m": hourly["temperature_2m"],
            "precipitation": hourly["precipitation"],
            "windspeed_10m": hourly["windspeed_10m"],
        })
        df["ingested_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("Transformed weather DataFrame: %d rows, %d cols", len(df), len(df.columns))
        return df

    def load(self, df: pd.DataFrame) -> str:
        """Write DataFrame as Parquet to S3 and return the s3_key. Skips if file already exists."""
        bucket = os.environ["S3_BUCKET"]
        # Key is hour-level so each run within the same hour is deduplicated
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H")
        s3_key = f"weather/{timestamp}/data.parquet"

        s3 = boto3.client("s3")

        # Check if file already exists — 404 means it doesn't, anything else is a real error
        try:
            s3.head_object(Bucket=bucket, Key=s3_key)
            logger.info("File already exists at s3://%s/%s — skipping upload", bucket, s3_key)
            return s3_key
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise

        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)

        s3.put_object(Bucket=bucket, Key=s3_key, Body=buffer.read())
        logger.info("Loaded weather data to s3://%s/%s", bucket, s3_key)
        return s3_key
