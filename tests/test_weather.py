"""Tests for WeatherPipeline."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.pipeline.weather import WeatherPipeline


MOCK_WEATHER_RESPONSE = {
    "hourly": {
        "time": [f"2024-01-01T{h:02d}:00" for h in range(24)],
        "temperature_2m": [20.0 + h * 0.1 for h in range(24)],
        "precipitation": [0.0] * 24,
        "windspeed_10m": [5.0 + h * 0.05 for h in range(24)],
    }
}


@patch("app.pipeline.weather.requests.get")
def test_extract_returns_dict(mock_get: MagicMock) -> None:
    """extract() should return a dict containing an 'hourly' key."""
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_WEATHER_RESPONSE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    pipeline = WeatherPipeline()
    result = pipeline.extract()

    assert isinstance(result, dict)
    assert "hourly" in result


def test_transform_returns_dataframe() -> None:
    """transform() should return a DataFrame with the expected columns."""
    pipeline = WeatherPipeline()
    df = pipeline.transform(MOCK_WEATHER_RESPONSE)

    assert isinstance(df, pd.DataFrame)
    expected_cols = {"time", "temperature_2m", "precipitation", "windspeed_10m", "ingested_at"}
    assert expected_cols.issubset(set(df.columns))


def test_transform_row_count() -> None:
    """transform() should produce exactly 24 rows (one per hour)."""
    pipeline = WeatherPipeline()
    df = pipeline.transform(MOCK_WEATHER_RESPONSE)
    assert len(df) == 24
