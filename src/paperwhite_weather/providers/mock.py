"""Deterministic fixture data for developing and testing skins without network access."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from typing import ClassVar

from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import (
    Condition,
    CurrentConditions,
    DailyForecast,
    HourlyForecast,
    SunTimes,
    WeatherSnapshot,
)
from paperwhite_weather.units import celsius_to_fahrenheit, kmh_to_mph, kmh_to_ms

# (condition, low °C, high °C, precipitation probability %, UV index max) for today and
# the next days.
_DAYS: tuple[tuple[Condition, float, float, float, float], ...] = (
    (Condition.PARTLY_CLOUDY, 14.0, 24.0, 10.0, 6.0),
    (Condition.RAIN, 12.0, 19.0, 80.0, 2.0),
    (Condition.THUNDERSTORM, 13.0, 21.0, 65.0, 3.0),
    (Condition.CLOUDY, 11.0, 18.0, 30.0, 4.0),
    (Condition.CLEAR, 9.0, 22.0, 0.0, 7.0),
)

_CURRENT_TEMPERATURE_C = 21.0
_CURRENT_FEELS_LIKE_C = 20.0
_CURRENT_WIND_KMH = 14.0
_CURRENT_HUMIDITY = 58.0
_CURRENT_UV_INDEX = 4.0
#: A fixed waxing gibbous moon, so the glyph shows a shape between quarter and full.
_MOON_PHASE = 0.38

#: Shape of the mock day: the temperature wave peaks at this local hour (and bottoms out
#: twelve hours earlier).
_WARMEST_HOUR = 15
#: Rain, when the day has any, is concentrated in this local-hour window.
_RAIN_HOURS = range(13, 20)

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
                uv_index_max=uv_max,
            )
            for offset, (condition, low, high, probability, uv_max) in enumerate(_DAYS)
        ]

        def at(clock: time) -> datetime:
            return datetime.combine(today, clock, tzinfo=location.tzinfo)

        hourly = [
            hour
            for day in daily
            for hour in _hourly_for_day(day, location, wind(_CURRENT_WIND_KMH))
        ]

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
                uv_index=_CURRENT_UV_INDEX,
            ),
            daily=daily,
            hourly=hourly,
            sun=SunTimes(
                civil_dawn=at(_CIVIL_DAWN),
                sunrise=at(_SUNRISE),
                sunset=at(_SUNSET),
                civil_dusk=at(_CIVIL_DUSK),
            ),
            moon_phase=_MOON_PHASE,
        )


def _hourly_for_day(day: DailyForecast, location: Location, wind: float) -> list[HourlyForecast]:
    """Twenty-four plausible hours for ``day``.

    A cosine wave between the day's low (at 3 in the morning) and high (at 15); rain in
    the afternoon window when the day's probability is 50 % or more, with the
    probability reduced outside that window; wind following the temperature.
    """
    midnight = datetime.combine(day.date, time(0), tzinfo=location.tzinfo)
    span = day.temperature_high - day.temperature_low
    hours = []
    for hour in range(24):
        phase = (hour - _WARMEST_HOUR) / 24 * 2 * math.pi
        temperature = day.temperature_low + span * (math.cos(phase) + 1) / 2
        raining = hour in _RAIN_HOURS and (day.precipitation_probability or 0) >= 50
        probability = day.precipitation_probability
        if probability is not None and hour not in _RAIN_HOURS:
            probability = round(probability * 0.25)
        hours.append(
            HourlyForecast(
                time=midnight + timedelta(hours=hour),
                temperature=round(temperature, 1),
                condition=day.condition if raining or day.condition in _DRY else Condition.CLOUDY,
                precipitation_probability=probability,
                wind_speed=round(wind * (0.6 + 0.4 * (math.cos(phase) + 1) / 2), 1),
            )
        )
    return hours


_DRY = frozenset({Condition.CLEAR, Condition.PARTLY_CLOUDY, Condition.CLOUDY, Condition.FOG})


def _identity(value: float) -> float:
    return value
