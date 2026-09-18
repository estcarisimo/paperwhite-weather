"""Skin interface and drawing helpers shared by skins."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Protocol

from PIL import Image, ImageDraw, ImageFont

from paperwhite_weather.config import Settings
from paperwhite_weather.fonts import Weight, load_font
from paperwhite_weather.models import Condition, WeatherSnapshot

#: Ink levels on an 8-bit grayscale canvas.
BLACK = 0
DARK_GRAY = 85
LIGHT_GRAY = 170
WHITE = 255

CONDITION_LABELS: dict[Condition, str] = {
    Condition.CLEAR: "Clear",
    Condition.PARTLY_CLOUDY: "Partly cloudy",
    Condition.CLOUDY: "Cloudy",
    Condition.FOG: "Fog",
    Condition.DRIZZLE: "Drizzle",
    Condition.RAIN: "Rain",
    Condition.SNOW: "Snow",
    Condition.THUNDERSTORM: "Storms",
    Condition.UNKNOWN: "—",
}


class Skin(Protocol):
    """A layout. Skins draw on a white ``"L"`` canvas of the requested size."""

    name: ClassVar[str]

    def compose(
        self,
        snapshot: WeatherSnapshot,
        settings: Settings,
        now: datetime,
        size: tuple[int, int],
    ) -> Image.Image:
        """Draw one frame.

        Parameters
        ----------
        snapshot
            The weather data to show.
        settings
            User configuration (units, time format, location label).
        now
            Current time, already converted to the location's time zone.
        size
            ``(width, height)`` of the canvas to draw on. This is the display's native size
            in portrait orientation and the transposed size in landscape.

        Returns
        -------
        PIL.Image.Image
            An ``"L"`` (8-bit grayscale) image exactly ``size`` pixels.
        """
        ...


def format_temperature(value: float) -> str:
    """Round to whole degrees and append the degree sign: ``"21°"``."""
    return f"{round(value)}°"


def format_clock(moment: datetime, time_format: str) -> str:
    """Format a time of day as ``"9:05 PM"`` (12h) or ``"21:05"`` (24h)."""
    if time_format == "12h":
        hour = moment.hour % 12 or 12
        return f"{hour}:{moment:%M} {moment:%p}"
    return f"{moment:%H:%M}"


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    weight: Weight,
    max_size: int,
    max_width: float,
    min_size: int = 8,
) -> ImageFont.FreeTypeFont:
    """Return the largest bundled font, at most ``max_size``, that fits ``text`` in ``max_width``.

    Parameters
    ----------
    draw
        The drawing context used to measure text.
    text
        The string that must fit on one line.
    weight
        ``"regular"`` or ``"bold"``.
    max_size, min_size
        Bounds for the font size in pixels. The search stops at ``min_size`` even if the
        text still does not fit, so a pathological string never loops forever.
    max_width
        Available width in pixels.
    """
    size = max(max_size, min_size)
    font = load_font(weight, size)
    while size > min_size and draw.textlength(text, font=font) > max_width:
        size = max(min_size, int(size * 0.92))
        font = load_font(weight, size)
    return font
