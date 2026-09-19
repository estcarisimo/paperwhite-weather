"""Sun and civil twilight times computed locally from coordinates."""

from __future__ import annotations

from datetime import date, datetime

from astral import LocationInfo
from astral.sun import dawn, dusk, sunrise, sunset

from paperwhite_weather.config import Location
from paperwhite_weather.models import SunTimes

#: Civil twilight: the sun's center is 6 degrees below the horizon.
CIVIL_DEPRESSION = 6.0


def compute_sun_times(location: Location, day: date) -> SunTimes:
    """Civil dawn, sunrise, sunset, and civil dusk for ``day`` at ``location``.

    Times are timezone-aware in the location's zone. Uses the ``astral`` package.

    Raises
    ------
    ValueError
        If the sun does not rise or set on that day at that latitude (polar day or night).
    """
    observer = LocationInfo(
        timezone=location.timezone, latitude=location.latitude, longitude=location.longitude
    ).observer
    tz = location.tzinfo
    return SunTimes(
        civil_dawn=_at(dawn(observer, date=day, tzinfo=tz, depression=CIVIL_DEPRESSION)),
        sunrise=_at(sunrise(observer, date=day, tzinfo=tz)),
        sunset=_at(sunset(observer, date=day, tzinfo=tz)),
        civil_dusk=_at(dusk(observer, date=day, tzinfo=tz, depression=CIVIL_DEPRESSION)),
    )


def _at(moment: datetime) -> datetime:
    """Drop sub-minute precision; the dashboard shows minutes."""
    return moment.replace(second=0, microsecond=0)
