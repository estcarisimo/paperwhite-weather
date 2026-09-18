"""The dashboard service: fetch on a schedule, render on demand, serve over HTTP.

The service keeps the last good :class:`WeatherSnapshot` and renders a frame for either
orientation whenever one is requested, so the clock on the frame is the request time and
a provider outage never blanks the display. Until the first successful fetch it serves an
"offline" frame that says so.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from typing import Literal

from PIL import Image

from paperwhite_weather import __version__
from paperwhite_weather.config import Orientation, Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.providers.base import WeatherProvider
from paperwhite_weather.render import render_dashboard, render_offline

logger = logging.getLogger(__name__)

#: Default TCP port. 8080 is commonly taken on home servers; 8765 is not registered.
DEFAULT_PORT = 8765
#: The service exists to be reached by the Kindle over the LAN, so it listens on every
#: interface by default; `--host` narrows it. Deliberate, hence the bandit exemption.
DEFAULT_HOST = "0.0.0.0"  # nosec B104
#: Value of ``service`` in ``/health``; clients use it to recognize this server on the LAN.
SERVICE_NAME = "paperwhite-weather"

ORIENTATIONS: tuple[Orientation, ...] = ("landscape", "portrait")
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class ServiceState:
    """What the service knows right now. Mutated only under :attr:`DashboardService._lock`."""

    snapshot: WeatherSnapshot | None = None
    fetched_at: datetime | None = None
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    refresh_count: int = 0
    failure_count: int = 0
    frames: dict[tuple[Orientation, str], bytes] = field(default_factory=dict)


class DashboardService:
    """Holds the weather cache and renders frames.

    Parameters
    ----------
    settings
        User configuration.
    provider
        Where weather comes from. ``fetch`` is called on every refresh.
    clock
        Returns the current UTC time; injectable for tests.
    """

    def __init__(
        self, settings: Settings, provider: WeatherProvider, clock: Clock = _utc_now
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.clock = clock
        self.state = ServiceState()
        self._lock = threading.Lock()

    def refresh(self) -> bool:
        """Fetch a new snapshot. Returns ``True`` on success; failures keep the last good one."""
        now = self.clock()
        try:
            snapshot = self.provider.fetch(self.settings.location, self.settings.units)
        except Exception as exc:  # noqa: BLE001 - the whole point is to survive any provider failure
            logger.error("Weather refresh failed: %s", exc)
            with self._lock:
                self.state.last_attempt_at = now
                self.state.last_error = f"{type(exc).__name__}: {exc}"
                self.state.failure_count += 1
            return False
        with self._lock:
            self.state.snapshot = snapshot
            self.state.fetched_at = snapshot.fetched_at
            self.state.last_attempt_at = now
            self.state.last_error = None
            self.state.refresh_count += 1
            self.state.frames.clear()
        logger.info("Weather refreshed from %r at %s", snapshot.source, snapshot.fetched_at)
        return True

    def frame(self, orientation: Orientation) -> bytes:
        """PNG bytes for ``orientation`` at the current minute, rendered from the cached snapshot.

        Frames are memoized per (orientation, minute), so many clients polling in the same
        minute cost one render.
        """
        now = self.clock()
        key = (orientation, now.strftime("%Y-%m-%dT%H:%M"))
        with self._lock:
            cached = self.state.frames.get(key)
            snapshot = self.state.snapshot
        if cached is not None:
            return cached
        display = self.settings.display.model_copy(update={"orientation": orientation})
        settings = self.settings.model_copy(update={"display": display})
        if snapshot is None:
            image = render_offline(settings, now, "No weather data yet")
        else:
            image = render_dashboard(snapshot, settings, now=now)
        data = _png_bytes(image)
        with self._lock:
            # Keep only the current minute; older keys are never requested again.
            self.state.frames = {k: v for k, v in self.state.frames.items() if k[1] == key[1]}
            self.state.frames[key] = data
        return data

    def health(self) -> dict[str, object]:
        """Identity and status document served at ``/health``."""
        with self._lock:
            state = self.state
            return {
                "service": SERVICE_NAME,
                "version": __version__,
                "status": "ok" if state.snapshot is not None else "no-data",
                "provider": self.provider.name,
                "skin": self.settings.display.skin,
                "default_orientation": self.settings.display.orientation,
                "orientations": list(ORIENTATIONS),
                "refresh_minutes": self.settings.display.refresh_minutes,
                "fetched_at": _iso(state.fetched_at),
                "last_attempt_at": _iso(state.last_attempt_at),
                "last_error": state.last_error,
                "refresh_count": state.refresh_count,
                "failure_count": state.failure_count,
            }

    def run_refresh_loop(self, stop: threading.Event) -> None:
        """Refresh now, then every ``refresh_minutes`` until ``stop`` is set."""
        interval = self.settings.display.refresh_minutes * 60
        while True:
            self.refresh()
            if stop.wait(interval):
                return


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value is not None else None


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes: ``/health``, ``/dashboard.png``, ``/dashboard/<orientation>.png``, ``/``."""

    server: DashboardServer  # narrowed for type checkers
    server_version = f"{SERVICE_NAME}/{__version__}"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        service = self.server.service
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send(HTTPStatus.OK, "application/json", json.dumps(service.health()).encode())
        elif path == "/dashboard.png":
            self._send_png(service.frame(service.settings.display.orientation))
        elif path.startswith("/dashboard/") and path.endswith(".png"):
            name = path[len("/dashboard/") : -len(".png")]
            if name not in ORIENTATIONS:
                self._send(HTTPStatus.NOT_FOUND, "text/plain", b"unknown orientation\n")
                return
            orientation: Literal["landscape", "portrait"] = (
                "landscape" if name == "landscape" else "portrait"
            )
            self._send_png(service.frame(orientation))
        elif path == "/":
            self._send(HTTPStatus.OK, "text/plain", _INDEX)
        else:
            self._send(HTTPStatus.NOT_FOUND, "text/plain", b"not found\n")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def _send_png(self, data: bytes) -> None:
        self._send(HTTPStatus.OK, "image/png", data)

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - base class signature
        logger.info("%s %s", self.address_string(), format % args)


_INDEX = b"""paperwhite-weather
  /health                    service identity and status (JSON)
  /dashboard.png             frame in the configured default orientation
  /dashboard/landscape.png   landscape frame
  /dashboard/portrait.png    portrait frame
"""


class DashboardServer(ThreadingHTTPServer):
    """HTTP server bound to a :class:`DashboardService`."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], service: DashboardService) -> None:
        super().__init__(address, DashboardHandler)
        self.service = service


def serve_forever(
    settings: Settings,
    provider: WeatherProvider,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    """Start the refresh loop and serve until interrupted (``KeyboardInterrupt``)."""
    service = DashboardService(settings, provider)
    stop = threading.Event()
    refresher = threading.Thread(
        target=service.run_refresh_loop, args=(stop,), name="refresh", daemon=True
    )
    refresher.start()
    with DashboardServer((host, port), service) as server:
        logger.info(
            "Serving on http://%s:%d/ (default orientation %s)",
            host,
            port,
            settings.display.orientation,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            stop.set()
