from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from paperwhite_weather.config import Location
from paperwhite_weather.sun import (
    compute_moon_phase,
    compute_sun_times,
    moon_illumination,
    moon_phase_name,
)

CHICAGO = Location(latitude=41.8781, longitude=-87.6298, timezone="America/Chicago")


@pytest.mark.math
def test_chicago_2026_09_18_matches_the_usno_table() -> None:
    """Independent reference: US Naval Observatory 'Rise/Set/Transit Times' API.

    ``https://aa.usno.navy.mil/api/rstt/oneday?date=2026-09-18&coords=41.8781,-87.6298&tz=-5``
    fetched 2026-09-19: Begin Civil Twilight 06:06, Rise 06:34, Set 18:55, End Civil
    Twilight 19:22 (UTC-5). The USNO rounds to the minute; allow one minute either way.
    """
    sun = compute_sun_times(CHICAGO, date(2026, 9, 18))
    expected = {
        "civil_dawn": (6, 6),
        "sunrise": (6, 34),
        "sunset": (18, 55),
        "civil_dusk": (19, 22),
    }
    for name, (hour, minute) in expected.items():
        moment: datetime = getattr(sun, name)
        assert moment.tzinfo is not None and moment.utcoffset() == timedelta(hours=-5)
        reference = moment.replace(hour=hour, minute=minute)
        assert abs(moment - reference) <= timedelta(minutes=1), f"{name}: {moment.time()}"


def test_times_are_in_the_location_zone_and_ordered() -> None:
    sun = compute_sun_times(CHICAGO, date(2026, 12, 21))
    assert sun.civil_dawn < sun.sunrise < sun.sunset < sun.civil_dusk
    assert sun.sunrise.tzinfo is not None
    assert sun.sunrise.utcoffset() == timedelta(hours=-6)  # standard time in December
    assert sun.sunrise.second == 0 and sun.sunrise.microsecond == 0


def test_polar_night_raises() -> None:
    svalbard = Location(latitude=78.2, longitude=15.6, timezone="Arctic/Longyearbyen")
    with pytest.raises(ValueError):
        compute_sun_times(svalbard, date(2026, 12, 21))


@pytest.mark.math
def test_moon_phase_pins_to_the_2026_eclipse_and_the_following_full_moon() -> None:
    """The total solar eclipse of 2026-08-12 is a new moon; 2026-09-26 is a full moon."""
    eclipse = compute_moon_phase(date(2026, 8, 12))
    assert eclipse > 0.96 or eclipse < 0.04
    assert abs(compute_moon_phase(date(2026, 9, 26)) - 0.5) < 0.04
    for day in range(1, 31):
        assert 0.0 <= compute_moon_phase(date(2026, 9, day)) < 1.0


def test_moon_illumination_and_names() -> None:
    assert moon_illumination(0.0) == 0.0
    assert abs(moon_illumination(0.25) - 0.5) < 1e-9
    assert abs(moon_illumination(0.5) - 1.0) < 1e-9
    assert [moon_phase_name(p) for p in (0.0, 0.12, 0.25, 0.38, 0.5, 0.62, 0.75, 0.88, 0.99)] == [
        "New moon",
        "Waxing crescent",
        "First quarter",
        "Waxing gibbous",
        "Full moon",
        "Waning gibbous",
        "Last quarter",
        "Waning crescent",
        "New moon",
    ]
