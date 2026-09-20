"""The dashboard service: fetch on a schedule, render on demand, serve over HTTP.

The service keeps the last good :class:`WeatherSnapshot` and renders a frame for either
orientation whenever one is requested, so the clock on the frame is the request time and
a provider outage never blanks the display. Until the first successful fetch it serves an
"offline" frame that says so.

The skin can be changed while the service runs (``POST /skin``, or the page at
``/skins`` from a phone); ``display.skin`` in the configuration is the skin at startup and
the choice is persisted in the state directory when one is given, so a restart keeps it.
"""

from __future__ import annotations

import html
import json
import logging
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs

from PIL import Image

from paperwhite_weather import __version__
from paperwhite_weather.config import Orientation, Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.providers.base import WeatherProvider
from paperwhite_weather.render import render_dashboard, render_offline
from paperwhite_weather.skins import available_skins

logger = logging.getLogger(__name__)

#: Default TCP port. 8080 is commonly taken on home servers; 8765 is not registered.
DEFAULT_PORT = 8765
#: Default configuration file for `paperwhite serve`, relative to the working directory.
DEFAULT_CONFIG = Path("config.yaml")
#: The service exists to be reached by the Kindle over the LAN, so it listens on every
#: interface by default; `--host` narrows it. Deliberate, hence the bandit exemption.
DEFAULT_HOST = "0.0.0.0"  # nosec B104
#: Value of ``service`` in ``/health``; clients use it to recognize this server on the LAN.
SERVICE_NAME = "paperwhite-weather"
#: File in the state directory that holds the skin chosen at runtime.
SKIN_STATE_FILE = "skin"

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
    skin: str = ""
    frames: dict[tuple[str, Orientation, str, str], bytes] = field(default_factory=dict)


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
    state_dir
        Directory where the skin chosen at runtime is persisted (created if missing).
        ``None`` keeps the choice in memory only, so a restart returns to
        ``settings.display.skin``.
    """

    def __init__(
        self,
        settings: Settings,
        provider: WeatherProvider,
        clock: Clock = _utc_now,
        state_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.clock = clock
        self.state = ServiceState(skin=settings.display.skin)
        self._lock = threading.Lock()
        self._skin_file = state_dir / SKIN_STATE_FILE if state_dir is not None else None
        self._load_skin()

    @property
    def skin(self) -> str:
        """The skin frames are rendered with right now."""
        with self._lock:
            return self.state.skin

    def set_skin(self, name: str) -> str:
        """Switch to ``name`` for every frame from now on and persist the choice.

        Raises
        ------
        ValueError
            If ``name`` is not a registered skin (nothing changes).
        """
        if name not in available_skins():
            raise ValueError(f"unknown skin {name!r}; available: {', '.join(available_skins())}")
        with self._lock:
            self.state.skin = name
        logger.info("Skin set to %r", name)
        self._save_skin(name)
        return name

    def next_skin(self) -> str:
        """Switch to the skin after the current one in ``available_skins()`` order, cyclically."""
        names = available_skins()
        current = self.skin
        index = names.index(current) if current in names else -1
        return self.set_skin(names[(index + 1) % len(names)])

    def _load_skin(self) -> None:
        if self._skin_file is None or not self._skin_file.is_file():
            return
        name = self._skin_file.read_text(encoding="utf-8").strip()
        if name in available_skins():
            self.state.skin = name
            logger.info("Skin %r restored from %s", name, self._skin_file)
        else:
            logger.warning("Ignoring unknown skin %r in %s", name, self._skin_file)

    def _save_skin(self, name: str) -> None:
        if self._skin_file is None:
            return
        try:
            self._skin_file.parent.mkdir(parents=True, exist_ok=True)
            self._skin_file.write_text(name + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist the skin to %s: %s", self._skin_file, exc)

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

        Frames are memoized per (skin, orientation, minute, snapshot), so many clients
        polling in the same minute cost one render, and a refresh that lands mid-render
        can never leave a frame of the previous snapshot in the cache.
        """
        now = self.clock()
        with self._lock:
            snapshot = self.state.snapshot
            last_attempt_at = self.state.last_attempt_at
            skin = self.state.skin
            key = (
                skin,
                orientation,
                now.strftime("%Y-%m-%dT%H:%M"),
                _snapshot_id(snapshot, last_attempt_at),
            )
            cached = self.state.frames.get(key)
        if cached is not None:
            return cached
        display = self.settings.display.model_copy(
            update={"orientation": orientation, "skin": skin}
        )
        settings = self.settings.model_copy(update={"display": display})
        if snapshot is None:
            image = render_offline(settings, last_attempt_at, "No weather data yet")
        else:
            image = render_dashboard(snapshot, settings, now=now)
        data = _png_bytes(image)
        with self._lock:
            if self.state.snapshot is not snapshot:
                return data  # a refresh landed meanwhile; serve this frame, cache nothing
            # Keep only the current minute; older keys are never requested again.
            self.state.frames = {k: v for k, v in self.state.frames.items() if k[2] == key[2]}
            self.state.frames[key] = data
        return data

    def health(self) -> dict[str, object]:
        """Identity and status document served at ``/health``."""
        with self._lock:
            state = self.state
            return {
                "service": SERVICE_NAME,
                "version": __version__,
                "hostname": socket.gethostname(),
                "status": "ok" if state.snapshot is not None else "no-data",
                "provider": self.provider.name,
                "skin": state.skin,
                "skins": available_skins(),
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


def _snapshot_id(snapshot: WeatherSnapshot | None, last_attempt_at: datetime | None) -> str:
    """Cache-key component that changes whenever the rendered content would change.

    With a snapshot, that is the snapshot itself; without one, the offline frame shows
    the last attempt time, so a new failed attempt must produce a new key.
    """
    if snapshot is None:
        return f"offline@{_iso(last_attempt_at)}"
    return f"{snapshot.source}@{snapshot.fetched_at.isoformat()}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value is not None else None


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    """Routes: ``/health``, ``/dashboard.png``, ``/dashboard/<orientation>.png``, ``/skins``,
    ``POST /skin``, ``POST /skin/next``, ``/``."""

    server: DashboardServer  # narrowed for type checkers
    server_version = f"{SERVICE_NAME}/{__version__}"

    def version_string(self) -> str:
        """``Server`` header without the Python version (and without the trailing space)."""
        return self.server_version

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
        elif path == "/skins":
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", _skins_page(service))
        elif path == "/":
            self._send(HTTPStatus.OK, "text/plain", _INDEX)
        else:
            self._send(HTTPStatus.NOT_FOUND, "text/plain", b"not found\n")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        """``POST /skin`` with a form field ``name`` (from the ``/skins`` page; answers with a
        redirect back to it), or ``POST /skin/<name>`` and ``POST /skin/next`` (answer JSON)."""
        service = self.server.service
        path = self.path.split("?", 1)[0]
        if path == "/skin":
            name = self._form().get("name", [""])[0]
            try:
                service.set_skin(name)
            except ValueError as exc:
                self._send(HTTPStatus.BAD_REQUEST, "text/plain", f"{exc}\n".encode())
                return
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/skins")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path.startswith("/skin/"):
            name = path[len("/skin/") :]
            try:
                skin = service.next_skin() if name == "next" else service.set_skin(name)
            except ValueError as exc:
                self._send(HTTPStatus.NOT_FOUND, "text/plain", f"{exc}\n".encode())
                return
            self._send(HTTPStatus.OK, "application/json", json.dumps({"skin": skin}).encode())
        else:
            self._send(HTTPStatus.NOT_FOUND, "text/plain", b"not found\n")

    def _form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(length, 4096)) if length else b""
        return parse_qs(body.decode("utf-8", errors="replace"))

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
  /skins                     choose the skin from a phone (HTML)
  POST /skin                 form field name=<skin>; redirects to /skins
  POST /skin/<name>          set the skin; POST /skin/next cycles; JSON {"skin": ...}
"""


_CURRENT = ' class="current"'


def _skins_page(service: DashboardService) -> bytes:
    """The ``/skins`` page: the current frame and one button per skin. No scripts."""
    current = service.skin
    following = _after(current)
    buttons = "\n".join(
        '<form method="post" action="/skin"><button name="name" '
        f'value="{html.escape(name)}"{_CURRENT if name == current else ""}>'
        f"{html.escape(name)}</button></form>"
        for name in available_skins()
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Paperwhite Weather: skins</title>
<style>
body{{font:18px/1.4 system-ui,sans-serif;margin:0;padding:16px;max-width:520px;
margin:auto;color:#111;background:#fff}}
h1{{font-size:20px;margin:0 0 12px}} p{{margin:0 0 12px;color:#555}}
img{{width:100%;height:auto;border:1px solid #ccc;display:block;margin-bottom:16px}}
form{{margin:0 0 8px}} button{{width:100%;padding:14px;font:inherit;font-size:20px;
border:2px solid #111;background:#fff;color:#111;border-radius:6px}}
button.current{{background:#111;color:#fff}} button.next{{border-style:dashed}}
</style></head><body>
<h1>Paperwhite Weather</h1>
<p>Skin now: <strong>{html.escape(current)}</strong>. The Kindle shows the new one at its
next refresh, or right away after a tap on the panel (which also flips the orientation).</p>
<img src="/dashboard/landscape.png" alt="the current frame, landscape">
{buttons}
<form method="post" action="/skin"><button class="next" name="name"
value="{html.escape(following)}">next: {html.escape(following)}</button></form>
</body></html>
"""
    return page.encode("utf-8")


def _after(name: str) -> str:
    names = available_skins()
    index = names.index(name) if name in names else -1
    return names[(index + 1) % len(names)]


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
    state_dir: Path | None = None,
) -> None:
    """Start the refresh loop and serve until interrupted (``KeyboardInterrupt``)."""
    service = DashboardService(settings, provider, state_dir=state_dir)
    if state_dir is None:
        logger.info("No state directory: a skin chosen at runtime is forgotten on restart")
    stop = threading.Event()
    refresher = threading.Thread(
        target=service.run_refresh_loop, args=(stop,), name="refresh", daemon=True
    )
    refresher.start()
    with DashboardServer((host, port), service) as server:
        logger.info(
            "Serving on http://%s:%d/ (skin %s, default orientation %s)",
            host,
            port,
            service.skin,
            settings.display.orientation,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            stop.set()
