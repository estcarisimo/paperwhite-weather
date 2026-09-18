"""Provider interface."""

from __future__ import annotations

from typing import ClassVar, Protocol

from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import WeatherSnapshot


class WeatherProvider(Protocol):
    """Fetches weather for a location and normalizes it into a snapshot.

    Implementations must raise on failure rather than return partial data; caching of the
    last good snapshot is the caller's job.
    """

    name: ClassVar[str]

    def fetch(self, location: Location, units: Units) -> WeatherSnapshot:
        """Return a fresh :class:`WeatherSnapshot` in the requested units."""
        ...
