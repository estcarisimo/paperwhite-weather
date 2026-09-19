from __future__ import annotations

from datetime import datetime, timezone

import pytest

from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import Condition
from paperwhite_weather.providers import available_providers, get_provider
from paperwhite_weather.providers.mock import MockProvider
from paperwhite_weather.units import celsius_to_fahrenheit, kmh_to_mph, kmh_to_ms
from tests.conftest import FIXED_NOW

LOCATION = Location(latitude=41.8781, longitude=-87.6298, timezone="America/Chicago")


def test_registry_lists_mock() -> None:
    assert "mock" in available_providers()
    assert isinstance(get_provider("mock"), MockProvider)


def test_unknown_provider_lists_available() -> None:
    with pytest.raises(ValueError, match="available: mock, open-meteo"):
        get_provider("nope")


def test_mock_is_deterministic_for_a_fixed_now() -> None:
    first = MockProvider(now=FIXED_NOW).fetch(LOCATION, Units())
    second = MockProvider(now=FIXED_NOW).fetch(LOCATION, Units())
    assert first == second
    assert first.fetched_at == FIXED_NOW
    assert first.source == "mock"


def test_mock_uses_local_date_for_today() -> None:
    # 03:30 UTC on the 19th is still the 18th in Chicago.
    now = datetime(2026, 9, 19, 3, 30, tzinfo=timezone.utc)
    snapshot = MockProvider(now=now).fetch(LOCATION, Units())
    assert snapshot.today.date.isoformat() == "2026-09-18"
    assert len(snapshot.daily) == 5
    assert snapshot.sun.sunrise.date().isoformat() == "2026-09-18"
    assert snapshot.sun.sunrise.tzinfo is not None


def test_mock_hourly_covers_every_day_within_its_range() -> None:
    snapshot = MockProvider(now=FIXED_NOW).fetch(LOCATION, Units())
    assert len(snapshot.hourly) == 24 * len(snapshot.daily)
    first = snapshot.hourly[0]
    assert first.time == datetime(2026, 9, 18, 0, 0, tzinfo=LOCATION.tzinfo)
    by_date = {day.date: day for day in snapshot.daily}
    for hour in snapshot.hourly:
        day = by_date[hour.time.date()]
        assert day.temperature_low <= hour.temperature <= day.temperature_high
        assert hour.wind_speed is not None and hour.wind_speed > 0
        assert hour.precipitation_probability is not None
    afternoon = [h for h in snapshot.hourly if h.time.date() == snapshot.daily[1].date]
    assert afternoon[15].condition is snapshot.daily[1].condition  # rain day, rain hour
    assert afternoon[3].condition is Condition.CLOUDY  # rain day, dry hour
    assert max(h.temperature for h in afternoon) == snapshot.daily[1].temperature_high


def test_mock_rejects_naive_now() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MockProvider(now=datetime(2026, 9, 18, 21, 45))


def test_mock_converts_units() -> None:
    metric = MockProvider(now=FIXED_NOW).fetch(LOCATION, Units())
    imperial = MockProvider(now=FIXED_NOW).fetch(
        LOCATION, Units(temperature="fahrenheit", wind="mph")
    )
    si_wind = MockProvider(now=FIXED_NOW).fetch(LOCATION, Units(wind="ms"))
    assert imperial.current.temperature == pytest.approx(
        celsius_to_fahrenheit(metric.current.temperature)
    )
    assert imperial.today.temperature_high == pytest.approx(
        celsius_to_fahrenheit(metric.today.temperature_high)
    )
    assert metric.current.wind_speed is not None
    assert imperial.current.wind_speed == pytest.approx(kmh_to_mph(metric.current.wind_speed))
    assert si_wind.current.wind_speed == pytest.approx(kmh_to_ms(metric.current.wind_speed))


@pytest.mark.math
@pytest.mark.parametrize(
    ("celsius", "fahrenheit"),
    [(0.0, 32.0), (100.0, 212.0), (-40.0, -40.0), (21.0, 69.8)],
)
def test_celsius_to_fahrenheit(celsius: float, fahrenheit: float) -> None:
    assert celsius_to_fahrenheit(celsius) == pytest.approx(fahrenheit)


@pytest.mark.math
def test_speed_conversions() -> None:
    assert kmh_to_mph(1.609344) == pytest.approx(1.0)
    assert kmh_to_ms(36.0) == pytest.approx(10.0)
