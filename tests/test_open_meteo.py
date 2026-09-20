from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import pairwise
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from paperwhite_weather.config import Location, Units
from paperwhite_weather.models import Condition
from paperwhite_weather.providers import available_providers, get_provider
from paperwhite_weather.providers.open_meteo import (
    WMO_CONDITIONS,
    OpenMeteoError,
    OpenMeteoProvider,
    build_query,
    condition_from_wmo,
    parse_forecast,
)

FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_chicago_2026-09-20.json"
CHICAGO = Location(latitude=41.8781, longitude=-87.6298, timezone="America/Chicago")
FETCHED = datetime(2026, 9, 20, 14, 1, tzinfo=timezone.utc)


@pytest.fixture
def payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_registry_lists_open_meteo() -> None:
    assert available_providers() == ["mock", "open-meteo"]
    assert isinstance(get_provider("open-meteo"), OpenMeteoProvider)


def test_build_query_requests_every_field_in_the_configured_units() -> None:
    query = build_query(CHICAGO, Units(temperature="fahrenheit", wind="mph"))
    assert query["latitude"] == "41.8781" and query["longitude"] == "-87.6298"
    assert query["timezone"] == "America/Chicago"
    assert query["temperature_unit"] == "fahrenheit" and query["wind_speed_unit"] == "mph"
    assert query["forecast_days"] == "5"
    for field in ("temperature_2m", "weather_code", "precipitation_probability"):
        assert field in query["current"].split(",")
    for field in ("weather_code", "temperature_2m_max", "temperature_2m_min"):
        assert field in query["daily"].split(",")
    for field in ("temperature_2m", "weather_code", "precipitation_probability", "wind_speed_10m"):
        assert field in query["hourly"].split(",")
    assert build_query(CHICAGO, Units(wind="ms"))["wind_speed_unit"] == "ms"


@pytest.mark.behaviour
def test_parse_recorded_response(payload: dict[str, object]) -> None:
    """Pins the normalization of a real response recorded on 2026-09-20 (metric units)."""
    snapshot = parse_forecast(payload, CHICAGO, Units(), fetched_at=FETCHED)
    assert snapshot.source == "open-meteo"
    assert snapshot.fetched_at == FETCHED
    assert snapshot.current.temperature == 18.2
    assert snapshot.current.feels_like == 17.8
    assert snapshot.current.humidity_percent == 95.0
    assert snapshot.current.wind_speed == 20.9
    assert snapshot.current.condition is Condition.DRIZZLE  # WMO 53
    assert snapshot.current.precipitation_probability == 70.0
    assert snapshot.current.uv_index == 0.15
    assert [day.date for day in snapshot.daily] == [date(2026, 9, 20 + i) for i in range(5)]
    assert [day.condition for day in snapshot.daily] == [
        Condition.RAIN,
        Condition.DRIZZLE,
        Condition.CLOUDY,
        Condition.CLOUDY,
        Condition.CLOUDY,
    ]
    assert [day.uv_index_max for day in snapshot.daily] == [0.7, 1.5, 5.5, 2.1, 5.4]
    # 2026-09-20 is nine days after the new moon of 2026-09-11: a waxing crescent
    # about a third of the way through the lunation.
    assert snapshot.moon_phase is not None and 0.25 < snapshot.moon_phase < 0.35
    today = snapshot.today
    assert (today.temperature_low, today.temperature_high) == (
        payload["daily"]["temperature_2m_min"][0],  # type: ignore[index]
        payload["daily"]["temperature_2m_max"][0],  # type: ignore[index]
    )
    # Sun times come from astral, not from the API; they must agree with the API's own
    # sunrise/sunset (an independent computation) within a minute. The API computes for
    # its grid cell (41.879, -87.650 in this response), not the exact coordinates.
    api_sunrise = datetime.fromisoformat(payload["daily"]["sunrise"][0])  # type: ignore[index]
    api_sunset = datetime.fromisoformat(payload["daily"]["sunset"][0])  # type: ignore[index]
    assert abs(snapshot.sun.sunrise.replace(tzinfo=None) - api_sunrise) <= timedelta(minutes=1)
    assert abs(snapshot.sun.sunset.replace(tzinfo=None) - api_sunset) <= timedelta(minutes=1)
    assert snapshot.sun.civil_dawn < snapshot.sun.sunrise
    assert snapshot.sun.sunset < snapshot.sun.civil_dusk


@pytest.mark.behaviour
def test_parse_recorded_hourly(payload: dict[str, object]) -> None:
    """Hourly rows are local midnight onward, made aware with the location's zone."""
    snapshot = parse_forecast(payload, CHICAGO, Units(), fetched_at=FETCHED)
    assert len(snapshot.hourly) == 120  # 5 days x 24 hours
    first = snapshot.hourly[0]
    assert first.time == datetime(2026, 9, 20, 0, 0, tzinfo=CHICAGO.tzinfo)
    assert first.time.utcoffset() == timedelta(hours=-5)
    assert first.temperature == 19.4
    assert first.condition is Condition.CLOUDY  # WMO 3
    assert first.precipitation_probability == 72.0
    assert first.wind_speed == 5.8
    assert snapshot.hourly[-1].time == datetime(2026, 9, 24, 23, 0, tzinfo=CHICAGO.tzinfo)
    assert all(a.time < b.time for a, b in pairwise(snapshot.hourly))


def test_hours_without_a_temperature_are_skipped(payload: dict[str, object]) -> None:
    hourly = payload["hourly"]
    assert isinstance(hourly, dict)
    hourly["temperature_2m"][-2:] = [None, None]
    hourly["precipitation_probability"][0] = None
    hourly["wind_speed_10m"][0] = None
    snapshot = parse_forecast(payload, CHICAGO, Units(), fetched_at=FETCHED)
    assert len(snapshot.hourly) == 118
    assert snapshot.hourly[0].precipitation_probability is None
    assert snapshot.hourly[0].wind_speed is None


@pytest.mark.parametrize(
    ("code", "condition"),
    [
        (0, Condition.CLEAR),
        (1, Condition.CLEAR),
        (2, Condition.PARTLY_CLOUDY),
        (3, Condition.CLOUDY),
        (45, Condition.FOG),
        (55, Condition.DRIZZLE),
        (65, Condition.RAIN),
        (75, Condition.SNOW),
        (82, Condition.RAIN),
        (86, Condition.SNOW),
        (99, Condition.THUNDERSTORM),
        (4, Condition.UNKNOWN),
        (None, Condition.UNKNOWN),
        ("3", Condition.UNKNOWN),
        (True, Condition.UNKNOWN),
    ],
)
def test_condition_from_wmo(code: object, condition: Condition) -> None:
    assert condition_from_wmo(code) is condition


def test_every_documented_wmo_code_is_mapped() -> None:
    """The codes Open-Meteo documents for its `weather_code` field."""
    documented = {0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77}
    documented |= {80, 81, 82, 85, 86, 95, 96, 99}
    assert set(WMO_CONDITIONS) == documented
    assert Condition.UNKNOWN not in WMO_CONDITIONS.values()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("daily"),
        lambda p: p["daily"].pop("temperature_2m_max"),
        lambda p: p["daily"]["time"].pop(),
        lambda p: p["daily"]["time"].clear() or p["daily"]["weather_code"].clear(),
        lambda p: p["daily"]["time"].__setitem__(0, "not-a-date"),
        lambda p: p["daily"]["temperature_2m_min"].__setitem__(1, None),
        lambda p: p["current"].pop("temperature_2m"),
        lambda p: p.pop("hourly"),
        lambda p: p["hourly"].pop("wind_speed_10m"),
        lambda p: p["hourly"]["time"].pop(),
        lambda p: p["hourly"]["time"].__setitem__(0, "2026-09-19T00:00+00:00"),
        lambda p: p["hourly"]["time"].__setitem__(0, "noon"),
        lambda p: p["daily"]["uv_index_max"].pop(),
    ],
)
def test_malformed_responses_raise(
    payload: dict[str, object], mutate: Callable[[dict[str, object]], object]
) -> None:
    mutate(payload)
    with pytest.raises(OpenMeteoError):
        parse_forecast(payload, CHICAGO, Units(), fetched_at=FETCHED)


def test_empty_daily_arrays_raise(payload: dict[str, object]) -> None:
    for key in list(payload["daily"]):  # type: ignore[union-attr]
        payload["daily"][key] = []  # type: ignore[index]
    with pytest.raises(OpenMeteoError, match="empty"):
        parse_forecast(payload, CHICAGO, Units(), fetched_at=FETCHED)


def test_optional_fields_may_be_missing(payload: dict[str, object]) -> None:
    current = payload["current"]
    assert isinstance(current, dict)
    for key in ("apparent_temperature", "relative_humidity_2m", "wind_speed_10m"):
        current.pop(key)
    current["precipitation_probability"] = None
    current.pop("uv_index")
    payload["daily"]["precipitation_probability_max"][2] = None  # type: ignore[index]
    payload["daily"].pop("uv_index_max")  # type: ignore[union-attr]
    snapshot = parse_forecast(payload, CHICAGO, Units(), fetched_at=FETCHED)
    assert snapshot.current.feels_like is None
    assert snapshot.current.humidity_percent is None
    assert snapshot.current.wind_speed is None
    assert snapshot.current.precipitation_probability is None
    assert snapshot.current.uv_index is None
    assert snapshot.daily[2].precipitation_probability is None
    assert all(day.uv_index_max is None for day in snapshot.daily)


# --- HTTP layer against a local stub server -------------------------------------------------


class _Stub(BaseHTTPRequestHandler):
    responses: list[tuple[int, bytes]] = []
    requests: list[dict[str, list[str]]] = []

    def do_GET(self) -> None:  # noqa: N802
        type(self).requests.append(parse_qs(urlparse(self.path).query))
        status, body = type(self).responses.pop(0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


@pytest.fixture
def stub() -> Iterator[str]:
    _Stub.responses = []
    _Stub.requests = []
    with HTTPServer(("127.0.0.1", 0), _Stub) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/v1/forecast"
        finally:
            httpd.shutdown()


def test_fetch_over_http(stub: str) -> None:
    _Stub.responses.append((200, FIXTURE.read_bytes()))
    before = datetime.now(tz=timezone.utc)
    snapshot = OpenMeteoProvider(url=stub).fetch(CHICAGO, Units(temperature="fahrenheit"))
    assert snapshot.source == "open-meteo"
    assert before <= snapshot.fetched_at <= datetime.now(tz=timezone.utc)
    assert snapshot.units.temperature == "fahrenheit"
    sent = _Stub.requests[0]
    assert sent["temperature_unit"] == ["fahrenheit"]
    assert sent["timezone"] == ["America/Chicago"]


def test_http_error_raises_with_the_reason(stub: str) -> None:
    _Stub.responses.append((400, b'{"error": true, "reason": "Latitude must be in range"}'))
    with pytest.raises(OpenMeteoError, match="HTTP 400.*Latitude"):
        OpenMeteoProvider(url=stub).fetch(CHICAGO, Units())


def test_error_document_with_200_raises(stub: str) -> None:
    _Stub.responses.append((200, b'{"error": true, "reason": "quota"}'))
    with pytest.raises(OpenMeteoError, match="quota"):
        OpenMeteoProvider(url=stub).fetch(CHICAGO, Units())


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]"])
def test_bad_json_raises(stub: str, body: bytes) -> None:
    _Stub.responses.append((200, body))
    with pytest.raises(OpenMeteoError):
        OpenMeteoProvider(url=stub).fetch(CHICAGO, Units())


def test_non_http_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="http"):
        OpenMeteoProvider(url="file:///etc/passwd")


def test_unreachable_host_raises() -> None:
    provider = OpenMeteoProvider(url="http://127.0.0.1:9/v1/forecast", timeout=2)
    with pytest.raises(OpenMeteoError, match="could not reach"):
        provider.fetch(CHICAGO, Units())
