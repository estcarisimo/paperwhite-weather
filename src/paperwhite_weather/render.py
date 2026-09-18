"""Turn a snapshot into a Kindle-ready grayscale image."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from PIL import Image, ImageDraw

from paperwhite_weather.config import Settings
from paperwhite_weather.fonts import load_font
from paperwhite_weather.models import WeatherSnapshot, require_aware
from paperwhite_weather.skins import get_skin
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, WHITE, format_clock

logger = logging.getLogger(__name__)

#: Gray levels the Kindle Paperwhite 3 panel can show.
EINK_GRAY_LEVELS = 16


def quantize_grayscale(image: Image.Image, levels: int = EINK_GRAY_LEVELS) -> Image.Image:
    """Snap an ``"L"`` image to ``levels`` evenly spaced gray values.

    Parameters
    ----------
    image
        An 8-bit grayscale image.
    levels
        Number of output gray levels, between 2 and 256.

    Returns
    -------
    PIL.Image.Image
        A new ``"L"`` image whose pixel values are multiples of ``255 / (levels - 1)``.
    """
    if image.mode != "L":
        raise ValueError(f"expected an 'L' image, got mode {image.mode!r}")
    if not 2 <= levels <= 256:
        raise ValueError(f"levels must be between 2 and 256, got {levels}")
    step = 255.0 / (levels - 1)
    table = [round(round(value / step) * step) for value in range(256)]
    return image.point(table)


def render_dashboard(
    snapshot: WeatherSnapshot,
    settings: Settings,
    now: datetime | None = None,
) -> Image.Image:
    """Render ``snapshot`` with the configured skin at the display's native size.

    Parameters
    ----------
    snapshot
        Weather data to draw.
    settings
        User configuration; selects the skin, orientation, and size.
    now
        Timezone-aware current time for the clock. Defaults to the current UTC time.

    Returns
    -------
    PIL.Image.Image
        An ``"L"`` image of ``settings.display.native_size`` pixels, quantized to the
        panel's gray levels. In landscape orientation the composed canvas is rotated 90°
        counterclockwise so it fits the portrait framebuffer.

    Raises
    ------
    ValueError
        If ``now`` is naive or the skin returns an image of the wrong size.
    """
    display = settings.display
    moment = require_aware(now) if now is not None else datetime.now(tz=timezone.utc)
    local_now = moment.astimezone(snapshot.location.tzinfo)

    skin = get_skin(display.skin)
    logger.info("Rendering skin %r on a %sx%s canvas", skin.name, *display.canvas_size)
    image = skin.compose(snapshot, settings, local_now, display.canvas_size)
    if image.size != display.canvas_size:
        raise ValueError(
            f"skin {skin.name!r} returned {image.size}, expected {display.canvas_size}"
        )
    if image.mode != "L":
        image = image.convert("L")
    if display.orientation == "landscape":
        image = image.rotate(90, expand=True)
    return quantize_grayscale(image)


def render_offline(
    settings: Settings, last_attempt_at: datetime | None, message: str
) -> Image.Image:
    """Render a frame that says there is no weather data, at the display's native size.

    Used by the service before the first successful fetch, so the device never shows a
    blank screen or a frame that pretends to be current.

    Parameters
    ----------
    settings
        User configuration; selects size, orientation, and time format.
    last_attempt_at
        When the service last tried to fetch weather (timezone-aware), or ``None`` if it
        has not tried yet. Shown on the frame so a long outage is visible as such.
    message
        Headline, for example ``"No weather data yet"``.

    Raises
    ------
    ValueError
        If ``last_attempt_at`` is naive.
    """
    display = settings.display
    width, height = display.canvas_size
    image = Image.new("L", (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    scale = min(width, height) / 1072
    if last_attempt_at is None:
        detail = "No fetch attempted yet"
    else:
        local = require_aware(last_attempt_at).astimezone(settings.location.tzinfo)
        detail = f"Last attempt {local:%a} {format_clock(local, display.time_format)}"
    draw.text(
        (width / 2, height * 0.42),
        message,
        font=load_font("bold", max(1, round(64 * scale))),
        fill=BLACK,
        anchor="mm",
    )
    draw.text(
        (width / 2, height * 0.42 + round(90 * scale)),
        detail,
        font=load_font("regular", max(1, round(36 * scale))),
        fill=DARK_GRAY,
        anchor="mm",
    )
    if display.orientation == "landscape":
        image = image.rotate(90, expand=True)
    return quantize_grayscale(image)
