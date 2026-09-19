from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from paperwhite_weather.config import Location
from paperwhite_weather.sun import compute_sun_times

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
