"""Shared fixtures."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from paperwhite_weather.config import Settings, load_settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.providers.mock import MockProvider

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG = REPO_ROOT / "config.example.yaml"

#: A fixed instant so renders and mock data are reproducible.
FIXED_NOW = datetime(2026, 9, 18, 21, 45, tzinfo=timezone.utc)


@pytest.fixture
def settings() -> Settings:
    return load_settings(EXAMPLE_CONFIG)


@pytest.fixture
def snapshot(settings: Settings) -> WeatherSnapshot:
    return MockProvider(now=FIXED_NOW).fetch(settings.location, settings.units)
