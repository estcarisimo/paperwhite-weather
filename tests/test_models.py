from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import (
    Condition,
    CurrentConditions,
    DailyForecast,
    HourlyForecast,
    SunTimes,
    WeatherSnapshot,
    require_aware,
)

UTC = timezone.utc
CHICAGO = ZoneInfo("America/Chicago")


def _day(offset: int) -> DailyForecast:
    return DailyForecast(
        date=date(2026, 9, 18) + timedelta(days=offset),
        condition=Condition.CLEAR,
        temperature_low=10.0,
        temperature_high=20.0,
    )


def _sun() -> SunTimes:
    base = datetime(2026, 9, 18, 6, 0, tzinfo=CHICAGO)
    return SunTimes(
        civil_dawn=base,
        sunrise=base + timedelta(minutes=30),
        sunset=base + timedelta(hours=13),
        civil_dusk=base + timedelta(hours=13, minutes=30),
    )


def _snapshot(**overrides: object) -> WeatherSnapshot:
    fields: dict[str, object] = {
        "fetched_at": datetime(2026, 9, 18, 21, 0, tzinfo=UTC),
        "source": "test",
        "location": Location(latitude=41.9, longitude=-87.6, timezone="America/Chicago"),
        "units": Units(),
        "current": CurrentConditions(temperature=15.0, condition=Condition.CLEAR),
        "daily": [_day(0), _day(1)],
        "sun": _sun(),
    }
    fields.update(overrides)
    return WeatherSnapshot.model_validate(fields)


def _hour(offset: int) -> HourlyForecast:
    return HourlyForecast(
        time=datetime(2026, 9, 18, 0, 0, tzinfo=CHICAGO) + timedelta(hours=offset),
        temperature=12.0,
        condition=Condition.CLOUDY,
    )


def test_hourly_defaults_to_empty_and_must_be_ascending_and_unique() -> None:
    assert _snapshot().hourly == []
    assert len(_snapshot(hourly=[_hour(0), _hour(1)]).hourly) == 2
    with pytest.raises(ValidationError, match="ascending"):
        _snapshot(hourly=[_hour(1), _hour(0)])
    with pytest.raises(ValidationError, match="ascending"):
        _snapshot(hourly=[_hour(0), _hour(0)])


def test_hourly_time_must_be_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        HourlyForecast(time=datetime(2026, 9, 18, 0, 0), temperature=1.0, condition=Condition.FOG)


def test_require_aware_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        require_aware(datetime(2026, 9, 18, 21, 0))


def test_fetched_at_must_be_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        _snapshot(fetched_at=datetime(2026, 9, 18, 16, 0, tzinfo=CHICAGO))
    with pytest.raises(ValidationError, match="timezone-aware"):
        _snapshot(fetched_at=datetime(2026, 9, 18, 21, 0))


def test_today_is_first_daily_entry() -> None:
    snapshot = _snapshot()
    assert snapshot.today == snapshot.daily[0]


def test_daily_must_be_ascending_and_unique() -> None:
    with pytest.raises(ValidationError, match="ascending"):
        _snapshot(daily=[_day(1), _day(0)])
    with pytest.raises(ValidationError, match="ascending"):
        _snapshot(daily=[_day(0), _day(0)])


def test_daily_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        _snapshot(daily=[])


def test_low_above_high_is_rejected() -> None:
    with pytest.raises(ValidationError, match="exceeds"):
        DailyForecast(
            date=date(2026, 9, 18),
            condition=Condition.RAIN,
            temperature_low=25.0,
            temperature_high=20.0,
        )


def test_sun_events_must_be_ordered_and_aware() -> None:
    sun = _sun()
    with pytest.raises(ValidationError, match="ordered"):
        SunTimes(
            civil_dawn=sun.sunrise,
            sunrise=sun.civil_dawn,
            sunset=sun.sunset,
            civil_dusk=sun.civil_dusk,
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        SunTimes(
            civil_dawn=datetime(2026, 9, 18, 6, 0),
            sunrise=sun.sunrise,
            sunset=sun.sunset,
            civil_dusk=sun.civil_dusk,
        )


@pytest.mark.parametrize("probability", [-1.0, 100.5])
def test_probabilities_are_percentages(probability: float) -> None:
    with pytest.raises(ValidationError):
        CurrentConditions(
            temperature=1.0, condition=Condition.RAIN, precipitation_probability=probability
        )
