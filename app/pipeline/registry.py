"""Pipeline registry — maps pipeline names to their classes."""

from .weather import WeatherPipeline

PIPELINE_REGISTRY: dict = {
    WeatherPipeline.name: WeatherPipeline,
}
