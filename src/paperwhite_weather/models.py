"""Provider-independent weather data model.

Every provider converts its API response into a :class:`WeatherSnapshot`; every skin
renders from one. All timestamps are timezone-aware, and :attr:`WeatherSnapshot.fetched_at`
is UTC so staleness is unambiguous.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from paperwhite_weather.config import Location, Units


class Condition(str, Enum):
    """Coarse sky condition, the common denominator across weather providers."""

    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    FOG = "fog"
    DRIZZLE = "drizzle"
    RAIN = "rain"
    SNOW = "snow"
    THUNDERSTORM = "thunderstorm"
    UNKNOWN = "unknown"


def require_aware(value: datetime) -> datetime:
    """Return ``value`` if it is timezone-aware, otherwise raise ``ValueError``."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


class CurrentConditions(BaseModel):
    """Observed or nowcast conditions at fetch time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature: float
    condition: Condition
    feels_like: float | None = None
    humidity_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    wind_speed: float | None = Field(default=None, ge=0.0)
    precipitation_probability: float | None = Field(default=None, ge=0.0, le=100.0)


class DailyForecast(BaseModel):
    """One calendar day of forecast in the location's time zone."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    condition: Condition
    temperature_low: float
    temperature_high: float
    precipitation_probability: float | None = Field(default=None, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _low_not_above_high(self) -> DailyForecast:
        if self.temperature_low > self.temperature_high:
            raise ValueError(
                f"temperature_low ({self.temperature_low}) exceeds "
                f"temperature_high ({self.temperature_high}) on {self.date}"
            )
        return self


class SunTimes(BaseModel):
    """Civil twilight and sun events for one day. All values timezone-aware."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    civil_dawn: datetime
    sunrise: datetime
    sunset: datetime
    civil_dusk: datetime

    _aware = field_validator("civil_dawn", "sunrise", "sunset", "civil_dusk")(require_aware)

    @model_validator(mode="after")
    def _ordered(self) -> SunTimes:
        events = [self.civil_dawn, self.sunrise, self.sunset, self.civil_dusk]
        if events != sorted(events):
            raise ValueError("sun events must be ordered dawn <= sunrise <= sunset <= dusk")
        return self


class WeatherSnapshot(BaseModel):
    """Everything a skin needs to draw one dashboard frame.

    Attributes
    ----------
    fetched_at
        When the data was obtained, in UTC. Skins show it so stale data is obvious.
    source
        Short provider name, for example ``"open-meteo"`` or ``"mock"``.
    daily
        Forecast starting with today; at least one entry.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fetched_at: datetime
    source: str = Field(min_length=1)
    location: Location
    units: Units
    current: CurrentConditions
    daily: list[DailyForecast] = Field(min_length=1)
    sun: SunTimes

    @field_validator("fetched_at")
    @classmethod
    def _fetched_at_utc(cls, value: datetime) -> datetime:
        require_aware(value)
        if value.utcoffset() != timedelta(0):
            raise ValueError("fetched_at must be in UTC")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _daily_sorted(self) -> WeatherSnapshot:
        dates = [day.date for day in self.daily]
        if dates != sorted(set(dates)):
            raise ValueError("daily forecasts must be in ascending order without duplicates")
        return self

    @property
    def today(self) -> DailyForecast:
        """The first entry of :attr:`daily`."""
        return self.daily[0]
