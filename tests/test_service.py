from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import ClassVar
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

import pytest
from PIL import Image

from paperwhite_weather import __version__
from paperwhite_weather.config import Location, Settings, Units
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.providers.mock import MockProvider
from paperwhite_weather.service import (
    SERVICE_NAME,
    SKIN_STATE_FILE,
    DashboardServer,
    DashboardService,
    serve_forever,
)
from paperwhite_weather.skins import available_skins
from tests.conftest import FIXED_NOW


class FailingProvider:
    name: ClassVar[str] = "failing"

    def fetch(self, location: Location, units: Units) -> WeatherSnapshot:
        raise ConnectionError("upstream unreachable")


class FlakyProvider:
    """Succeeds once, then fails forever."""

    name: ClassVar[str] = "flaky"

    def __init__(self) -> None:
        self.calls = 0
        self._good = MockProvider(now=FIXED_NOW)

    def fetch(self, location: Location, units: Units) -> WeatherSnapshot:
        self.calls += 1
        if self.calls > 1:
            raise TimeoutError("second call fails")
        return self._good.fetch(location, units)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: int) -> None:
        self.now += timedelta(**kwargs)


def _png_size(data: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as image:
        assert image.format == "PNG"
        assert image.mode == "L"
        return image.size


def test_offline_frame_before_first_refresh(settings: Settings) -> None:
    clock = FakeClock(FIXED_NOW)
    service = DashboardService(settings, FailingProvider(), clock=clock)
    never = service.frame("landscape")
    assert _png_size(never) == (1072, 1448)
    assert _png_size(service.frame("portrait")) == (1072, 1448)
    health = service.health()
    assert health["service"] == SERVICE_NAME
    assert health["status"] == "no-data"
    assert health["fetched_at"] is None

    assert service.refresh() is False
    attempted = service.frame("landscape")
    assert attempted != never, "the offline frame shows the last attempt once there is one"
    clock.advance(minutes=45)
    later = service.frame("landscape")
    assert later == attempted, "the offline frame shows the attempt time, not the request time"


def test_offline_frame_text_is_the_last_attempt(settings: Settings) -> None:
    from paperwhite_weather.render import render_offline

    never = render_offline(settings, None, "No weather data yet")
    at = render_offline(settings, FIXED_NOW, "No weather data yet")
    later = render_offline(settings, FIXED_NOW + timedelta(minutes=45), "No weather data yet")
    assert never.size == at.size == (1072, 1448)
    assert never.tobytes() != at.tobytes() != later.tobytes()
    with pytest.raises(ValueError, match="timezone-aware"):
        render_offline(settings, datetime(2026, 9, 18, 21, 45), "x")


def test_refresh_success_then_failure_keeps_last_good(settings: Settings) -> None:
    provider = FlakyProvider()
    clock = FakeClock(FIXED_NOW)
    service = DashboardService(settings, provider, clock=clock)

    assert service.refresh() is True
    first = service.frame("landscape")
    health = service.health()
    assert health["status"] == "ok"
    assert health["fetched_at"] == FIXED_NOW.isoformat(timespec="seconds")
    assert health["refresh_count"] == 1 and health["failure_count"] == 0

    clock.advance(minutes=15)
    assert service.refresh() is False
    health = service.health()
    assert health["status"] == "ok", "a failed refresh must not drop the cached snapshot"
    assert health["fetched_at"] == FIXED_NOW.isoformat(timespec="seconds")
    assert health["last_error"] == "TimeoutError: second call fails"
    assert health["failure_count"] == 1
    assert health["last_attempt_at"] == (FIXED_NOW + timedelta(minutes=15)).isoformat(
        timespec="seconds"
    )
    later = service.frame("landscape")
    assert later != first, "the clock on the frame moves even when the data is cached"


def test_frames_are_memoized_per_minute(settings: Settings) -> None:
    clock = FakeClock(FIXED_NOW)
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), clock=clock)
    service.refresh()
    a = service.frame("portrait")
    clock.advance(seconds=20)
    assert service.frame("portrait") is a
    clock.advance(seconds=60)
    b = service.frame("portrait")
    assert b is not a
    assert {key[:3] for key in service.state.frames} == {
        ("minimal", "portrait", clock.now.strftime("%Y-%m-%dT%H:%M"))
    }


def test_skin_defaults_to_config_and_switches(settings: Settings) -> None:
    clock = FakeClock(FIXED_NOW)
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), clock=clock)
    service.refresh()
    assert service.skin == settings.display.skin == "minimal"
    before = service.frame("landscape")
    assert service.set_skin("newspaper") == "newspaper"
    assert service.skin == "newspaper"
    assert service.health()["skin"] == "newspaper"
    after = service.frame("landscape")
    assert after != before, "the same minute must render the new skin, not the memoized frame"
    assert _png_size(after) == (1072, 1448)
    service.set_skin("minimal")
    assert service.frame("landscape") == before


def test_next_skin_cycles_in_registry_order(settings: Settings) -> None:
    service = DashboardService(settings, MockProvider(now=FIXED_NOW))
    names = available_skins()
    seen = [service.next_skin() for _ in names]
    start = names.index("minimal")
    assert seen == names[start + 1 :] + names[: start + 1]
    assert service.skin == "minimal"


def test_set_skin_rejects_unknown_names(settings: Settings) -> None:
    service = DashboardService(settings, MockProvider(now=FIXED_NOW))
    with pytest.raises(ValueError, match="unknown skin 'neon'"):
        service.set_skin("neon")
    assert service.skin == "minimal"


def test_skin_is_persisted_in_the_state_dir(settings: Settings, tmp_path: Path) -> None:
    state_dir = tmp_path / "state"  # does not exist yet; the service creates it
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), state_dir=state_dir)
    service.set_skin("graphic")
    assert (state_dir / SKIN_STATE_FILE).read_text() == "graphic\n"
    restarted = DashboardService(settings, MockProvider(now=FIXED_NOW), state_dir=state_dir)
    assert restarted.skin == "graphic"
    assert restarted.health()["skin"] == "graphic"


def test_unknown_persisted_skin_is_ignored(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / SKIN_STATE_FILE).write_text("gone\n")
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), state_dir=tmp_path)
    assert service.skin == "minimal"
    assert "Ignoring unknown skin 'gone'" in caplog.text


def test_unwritable_state_dir_does_not_break_switching(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), state_dir=blocker)
    assert service.set_skin("forecast") == "forecast"
    assert service.skin == "forecast"
    assert "Could not persist the skin" in caplog.text


def test_refresh_during_render_does_not_cache_a_stale_frame(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refresh that lands while a frame is rendering must not poison the cache."""
    import paperwhite_weather.service as service_module

    clock = FakeClock(FIXED_NOW)
    first = MockProvider(now=FIXED_NOW)
    second = MockProvider(now=FIXED_NOW + timedelta(minutes=10))
    service = DashboardService(settings, first, clock=clock)
    service.refresh()

    real_render = service_module.render_dashboard
    refreshed = False

    def render_and_refresh(*args: object, **kwargs: object) -> Image.Image:
        nonlocal refreshed
        if not refreshed:
            refreshed = True
            service.provider = second
            service.refresh()  # swaps the snapshot mid-render
        return real_render(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(service_module, "render_dashboard", render_and_refresh)
    stale = service.frame("landscape")
    assert service.state.frames == {}, "a frame of the replaced snapshot must not be cached"
    fresh = service.frame("landscape")
    assert fresh != stale
    assert service.frame("landscape") is fresh


def test_refresh_loop_stops(settings: Settings) -> None:
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), clock=FakeClock(FIXED_NOW))
    stop = threading.Event()
    stop.set()  # loop body runs once, then exits without waiting
    service.run_refresh_loop(stop)
    assert service.health()["refresh_count"] == 1


@pytest.fixture
def server(settings: Settings) -> Iterator[str]:
    service = DashboardService(settings, MockProvider(now=FIXED_NOW), clock=FakeClock(FIXED_NOW))
    service.refresh()
    with DashboardServer(("127.0.0.1", 0), service) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()


def _get(url: str, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    with urlopen(Request(url, method=method), timeout=5) as response:  # noqa: S310 - loopback
        return response.status, dict(response.headers), response.read()


def test_http_health(server: str) -> None:
    status, headers, body = _get(f"{server}/health")
    assert status == 200
    assert headers["Server"] == f"{SERVICE_NAME}/{__version__}"
    assert headers["Content-Type"] == "application/json"
    assert headers["Cache-Control"] == "no-store"
    document = json.loads(body)
    assert document["service"] == SERVICE_NAME
    assert document["hostname"] == socket.gethostname()
    assert document["orientations"] == ["landscape", "portrait"]
    assert document["default_orientation"] == "landscape"


@pytest.mark.parametrize(
    "path", ["/dashboard.png", "/dashboard/landscape.png", "/dashboard/portrait.png"]
)
def test_http_frames_are_native_size(server: str, path: str) -> None:
    status, headers, body = _get(f"{server}{path}")
    assert status == 200
    assert headers["Content-Type"] == "image/png"
    assert int(headers["Content-Length"]) == len(body)
    assert _png_size(body) == (1072, 1448)


def test_http_default_orientation_matches_config(server: str) -> None:
    _, _, default = _get(f"{server}/dashboard.png")
    _, _, landscape = _get(f"{server}/dashboard/landscape.png")
    _, _, portrait = _get(f"{server}/dashboard/portrait.png")
    assert default == landscape
    assert default != portrait


def test_http_head_and_index(server: str) -> None:
    status, headers, body = _get(f"{server}/dashboard/portrait.png", method="HEAD")
    assert status == 200 and body == b"" and int(headers["Content-Length"]) > 0
    status, _, body = _get(f"{server}/")
    assert status == 200 and b"/health" in body


@pytest.mark.parametrize("path", ["/dashboard/sideways.png", "/nope", "/dashboard/"])
def test_http_404(server: str, path: str) -> None:
    with pytest.raises(HTTPError) as excinfo:
        _get(f"{server}{path}")
    assert excinfo.value.code == 404


def _post(url: str, data: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    request = Request(url, data=data if data is not None else b"", method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    opener = build_opener(_NoRedirect)
    with opener.open(request, timeout=5) as response:  # noqa: S310 - loopback
        return response.status, dict(response.headers), response.read()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def test_http_skins_page_lists_every_skin(server: str) -> None:
    status, headers, body = _get(f"{server}/skins")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    page = body.decode()
    for name in available_skins():
        assert f'value="{name}"' in page
    assert "<script" not in page
    assert 'class="current"' in page or "class=current" in page
    assert 'src="/dashboard/landscape.png"' in page


def test_http_post_skin_form_redirects_and_switches(server: str) -> None:
    _, _, before = _get(f"{server}/dashboard/landscape.png")
    with pytest.raises(HTTPError) as excinfo:
        _post(f"{server}/skin", b"name=timeline")
    assert excinfo.value.code == 303
    assert excinfo.value.headers["Location"] == "/skins"
    assert json.loads(_get(f"{server}/health")[2])["skin"] == "timeline"
    _, _, after = _get(f"{server}/dashboard/landscape.png")
    assert after != before
    with pytest.raises(HTTPError) as excinfo:
        _post(f"{server}/skin", b"name=neon")
    assert excinfo.value.code == 400
    assert json.loads(_get(f"{server}/health")[2])["skin"] == "timeline"


def test_http_post_skin_path_and_next(server: str) -> None:
    status, headers, body = _post(f"{server}/skin/big-clock")
    assert status == 200 and headers["Content-Type"] == "application/json"
    assert json.loads(body) == {"skin": "big-clock"}
    names = available_skins()
    following = names[(names.index("big-clock") + 1) % len(names)]
    assert json.loads(_post(f"{server}/skin/next")[2]) == {"skin": following}
    assert json.loads(_get(f"{server}/health")[2])["skin"] == following
    with pytest.raises(HTTPError) as excinfo:
        _post(f"{server}/skin/neon")
    assert excinfo.value.code == 404
    with pytest.raises(HTTPError) as excinfo:
        _post(f"{server}/health")
    assert excinfo.value.code == 404


def test_http_get_does_not_switch(server: str) -> None:
    with pytest.raises(HTTPError) as excinfo:
        _get(f"{server}/skin/next")
    assert excinfo.value.code == 404
    assert json.loads(_get(f"{server}/health")[2])["skin"] == "minimal"


def test_serve_forever_shuts_down_on_keyboard_interrupt(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt(self: DashboardServer) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(DashboardServer, "serve_forever", interrupt)
    serve_forever(settings, MockProvider(now=FIXED_NOW), host="127.0.0.1", port=0)


def test_utc_clock_default(settings: Settings) -> None:
    service = DashboardService(settings, MockProvider())
    assert service.clock().tzinfo is timezone.utc
