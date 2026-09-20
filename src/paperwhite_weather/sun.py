"""Sun and civil twilight times computed locally from coordinates."""

from __future__ import annotations

import math
from datetime import date, datetime

from astral import LocationInfo, moon
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


#: Astral counts the lunation in days from the new moon, up to (not including) this.
_LUNATION_DAYS = 28.0
_PHASE_NAMES = (
    "New moon",
    "Waxing crescent",
    "First quarter",
    "Waxing gibbous",
    "Full moon",
    "Waning gibbous",
    "Last quarter",
    "Waning crescent",
)


def compute_moon_phase(day: date) -> float:
    """The moon's phase on ``day`` as a fraction of the lunation.

    Parameters
    ----------
    day
        Calendar date.

    Returns
    -------
    float
        ``0`` at the new moon, ``0.25`` at the first quarter, ``0.5`` at the full moon,
        ``0.75`` at the last quarter; always in ``[0, 1)``.
    """
    return (moon.phase(day) % _LUNATION_DAYS) / _LUNATION_DAYS


def moon_illumination(phase: float) -> float:
    """Fraction of the disc that is lit for ``phase`` (``0`` new, ``1`` full)."""
    return (1 - math.cos(2 * math.pi * phase)) / 2


def moon_phase_name(phase: float) -> str:
    """Conventional name of the phase: quarters within a sixteenth of the lunation."""
    index = round(phase * 8) % 8
    return _PHASE_NAMES[index]
