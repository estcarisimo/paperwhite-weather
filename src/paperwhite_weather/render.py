"""Turn a snapshot into a Kindle-ready grayscale image."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import WeatherSnapshot, require_aware
from paperwhite_weather.skins import get_skin

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
