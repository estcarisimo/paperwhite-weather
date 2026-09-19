"""Open-Meteo provider: https://open-meteo.com/ (no API key for non-commercial use)."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any, ClassVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paperwhite_weather import __version__
from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import (
    Condition,
    CurrentConditions,
    DailyForecast,
    WeatherSnapshot,
)
from paperwhite_weather.sun import compute_sun_times

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 5
TIMEOUT_SECONDS = 15.0

_CURRENT_FIELDS = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "wind_speed_10m",
    "weather_code",
    "precipitation_probability",
)
_DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
)
_WIND_UNIT = {"kmh": "kmh", "mph": "mph", "ms": "ms"}

#: WMO weather interpretation codes (WW), as documented by Open-Meteo, to our conditions.
WMO_CONDITIONS: dict[int, Condition] = {
    0: Condition.CLEAR,
    1: Condition.CLEAR,  # mainly clear
    2: Condition.PARTLY_CLOUDY,
    3: Condition.CLOUDY,  # overcast
    45: Condition.FOG,
    48: Condition.FOG,  # depositing rime fog
    51: Condition.DRIZZLE,
    53: Condition.DRIZZLE,
    55: Condition.DRIZZLE,
    56: Condition.DRIZZLE,  # freezing drizzle
    57: Condition.DRIZZLE,
    61: Condition.RAIN,
    63: Condition.RAIN,
    65: Condition.RAIN,
    66: Condition.RAIN,  # freezing rain
    67: Condition.RAIN,
    71: Condition.SNOW,
    73: Condition.SNOW,
    75: Condition.SNOW,
    77: Condition.SNOW,  # snow grains
    80: Condition.RAIN,  # rain showers
    81: Condition.RAIN,
    82: Condition.RAIN,
    85: Condition.SNOW,  # snow showers
    86: Condition.SNOW,
    95: Condition.THUNDERSTORM,
    96: Condition.THUNDERSTORM,  # with slight hail
    99: Condition.THUNDERSTORM,  # with heavy hail
}


class OpenMeteoError(RuntimeError):
    """The Open-Meteo request failed or its response was not usable."""


def condition_from_wmo(code: object) -> Condition:
    """Map a WMO weather code to a :class:`Condition`; unknown codes become ``UNKNOWN``."""
    if isinstance(code, bool) or not isinstance(code, int):
        return Condition.UNKNOWN
    return WMO_CONDITIONS.get(code, Condition.UNKNOWN)


def build_query(location: Location, units: Units) -> dict[str, str]:
    """Query parameters for the forecast endpoint. Exposed for tests and debugging."""
    return {
        "latitude": f"{location.latitude:.4f}",
        "longitude": f"{location.longitude:.4f}",
        "timezone": location.timezone,
        "current": ",".join(_CURRENT_FIELDS),
        "daily": ",".join(_DAILY_FIELDS),
        "forecast_days": str(FORECAST_DAYS),
        "temperature_unit": units.temperature,
        "wind_speed_unit": _WIND_UNIT[units.wind],
    }


class OpenMeteoProvider:
    """Fetch current conditions and a daily forecast from Open-Meteo.

    Sun times are computed locally (:mod:`paperwhite_weather.sun`) rather than taken from
    the API, because the API has no civil twilight.

    Parameters
    ----------
    url
        Forecast endpoint; override to point at a mock server.
    timeout
        Socket timeout in seconds.
    """

    name: ClassVar[str] = "open-meteo"

    def __init__(self, url: str = FORECAST_URL, timeout: float = TIMEOUT_SECONDS) -> None:
        self.url = url
        self.timeout = timeout

    def fetch(self, location: Location, units: Units) -> WeatherSnapshot:
        """Request the forecast and normalize it. Raises :class:`OpenMeteoError` on failure."""
        payload = self._request(build_query(location, units))
        return parse_forecast(payload, location, units, fetched_at=datetime.now(tz=timezone.utc))

    def _request(self, query: Mapping[str, str]) -> dict[str, Any]:
        request = Request(
            f"{self.url}?{urlencode(query)}",
            headers={
                "User-Agent": f"paperwhite-weather/{__version__}",
                "Accept": "application/json",
            },
        )
        logger.debug("GET %s", request.full_url)
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - https, fixed host
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise OpenMeteoError(f"HTTP {exc.code} from Open-Meteo: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise OpenMeteoError(f"could not reach Open-Meteo: {exc}") from exc
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise OpenMeteoError("Open-Meteo returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise OpenMeteoError("Open-Meteo returned a non-object JSON document")
        if payload.get("error"):
            raise OpenMeteoError(f"Open-Meteo error: {payload.get('reason', 'unknown')}")
        return payload


def parse_forecast(
    payload: Mapping[str, Any], location: Location, units: Units, fetched_at: datetime
) -> WeatherSnapshot:
    """Convert a forecast response into a :class:`WeatherSnapshot`.

    Parameters
    ----------
    payload
        Decoded JSON from the forecast endpoint, requested with :func:`build_query`.
    location, units
        What the request was made for; recorded on the snapshot.
    fetched_at
        When the response was obtained (UTC).

    Raises
    ------
    OpenMeteoError
        If a required field is missing or malformed.
    """
    try:
        current = payload["current"]
        daily = payload["daily"]
        days = [date.fromisoformat(value) for value in daily["time"]]
        codes = daily["weather_code"]
        highs = daily["temperature_2m_max"]
        lows = daily["temperature_2m_min"]
        probabilities = daily["precipitation_probability_max"]
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenMeteoError(f"unexpected Open-Meteo response shape: {exc!r}") from exc
    if not days or not (len(days) == len(codes) == len(highs) == len(lows) == len(probabilities)):
        raise OpenMeteoError("Open-Meteo daily arrays are empty or of unequal length")

    forecasts = []
    rows = zip(days, codes, highs, lows, probabilities, strict=True)
    for day, code, high, low, probability in rows:
        if high is None or low is None:
            raise OpenMeteoError(f"Open-Meteo has no temperature range for {day}")
        forecasts.append(
            DailyForecast(
                date=day,
                condition=condition_from_wmo(code),
                temperature_low=float(low),
                temperature_high=float(high),
                precipitation_probability=_optional_float(probability),
            )
        )

    temperature = current.get("temperature_2m")
    if temperature is None:
        raise OpenMeteoError("Open-Meteo has no current temperature")
    return WeatherSnapshot(
        fetched_at=fetched_at,
        source=OpenMeteoProvider.name,
        location=location,
        units=units,
        current=CurrentConditions(
            temperature=float(temperature),
            condition=condition_from_wmo(current.get("weather_code")),
            feels_like=_optional_float(current.get("apparent_temperature")),
            humidity_percent=_optional_float(current.get("relative_humidity_2m")),
            wind_speed=_optional_float(current.get("wind_speed_10m")),
            precipitation_probability=_optional_float(current.get("precipitation_probability")),
        ),
        daily=forecasts,
        sun=compute_sun_times(location, days[0]),
    )


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None
