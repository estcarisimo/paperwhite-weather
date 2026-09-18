"""Deterministic fixture data for developing and testing skins without network access."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import ClassVar

from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import (
    Condition,
    CurrentConditions,
    DailyForecast,
    SunTimes,
    WeatherSnapshot,
)
from paperwhite_weather.units import celsius_to_fahrenheit, kmh_to_mph, kmh_to_ms

# (condition, low °C, high °C, precipitation probability %) for today and the next days.
_DAYS: tuple[tuple[Condition, float, float, float], ...] = (
    (Condition.PARTLY_CLOUDY, 14.0, 24.0, 10.0),
    (Condition.RAIN, 12.0, 19.0, 80.0),
    (Condition.THUNDERSTORM, 13.0, 21.0, 65.0),
    (Condition.CLOUDY, 11.0, 18.0, 30.0),
    (Condition.CLEAR, 9.0, 22.0, 0.0),
)

_CURRENT_TEMPERATURE_C = 21.0
_CURRENT_FEELS_LIKE_C = 20.0
_CURRENT_WIND_KMH = 14.0
_CURRENT_HUMIDITY = 58.0

_CIVIL_DAWN = time(6, 12)
_SUNRISE = time(6, 40)
_SUNSET = time(19, 5)
_CIVIL_DUSK = time(19, 33)


class MockProvider:
    """A provider that returns the same plausible early-autumn forecast every time.

    Parameters
    ----------
    now
        Timezone-aware moment to treat as "now". Defaults to the current UTC time. Passing
        a fixed value makes renders reproducible.
    """

    name: ClassVar[str] = "mock"

    def __init__(self, now: datetime | None = None) -> None:
        if now is not None and (now.tzinfo is None or now.utcoffset() is None):
            raise ValueError("now must be timezone-aware")
        self._now = now

    def fetch(self, location: Location, units: Units) -> WeatherSnapshot:
        """Build the fixture snapshot for ``location`` in ``units``."""
        now = self._now or datetime.now(tz=timezone.utc)
        local_now = now.astimezone(location.tzinfo)
        today = local_now.date()

        convert = celsius_to_fahrenheit if units.temperature == "fahrenheit" else _identity
        wind = {"kmh": _identity, "mph": kmh_to_mph, "ms": kmh_to_ms}[units.wind]

        daily = [
            DailyForecast(
                date=today + timedelta(days=offset),
                condition=condition,
                temperature_low=convert(low),
                temperature_high=convert(high),
                precipitation_probability=probability,
            )
            for offset, (condition, low, high, probability) in enumerate(_DAYS)
        ]

        def at(clock: time) -> datetime:
            return datetime.combine(today, clock, tzinfo=location.tzinfo)

        return WeatherSnapshot(
            fetched_at=now.astimezone(timezone.utc),
            source=self.name,
            location=location,
            units=units,
            current=CurrentConditions(
                temperature=convert(_CURRENT_TEMPERATURE_C),
                feels_like=convert(_CURRENT_FEELS_LIKE_C),
                condition=daily[0].condition,
                humidity_percent=_CURRENT_HUMIDITY,
                wind_speed=wind(_CURRENT_WIND_KMH),
                precipitation_probability=daily[0].precipitation_probability,
            ),
            daily=daily,
            sun=SunTimes(
                civil_dawn=at(_CIVIL_DAWN),
                sunrise=at(_SUNRISE),
                sunset=at(_SUNSET),
                civil_dusk=at(_CIVIL_DUSK),
            ),
        )


def _identity(value: float) -> float:
    return value
