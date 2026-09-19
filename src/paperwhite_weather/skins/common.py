"""Drawing helpers shared by skins: scaled measurements, text, rules, icons, formatting.

A skin composes on a canvas of arbitrary size. ``Canvas`` maps a design made for the
Paperwhite 3 (1072x1448 portrait, 1448x1072 landscape) onto that size so a skin written
once renders correctly on other panels and in both orientations.
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image, ImageDraw

from paperwhite_weather.config import Settings
from paperwhite_weather.fonts import Weight, load_font
from paperwhite_weather.icons import draw_icon
from paperwhite_weather.models import Condition, DailyForecast, WeatherSnapshot
from paperwhite_weather.skins.base import (
    BLACK,
    CONDITION_LABELS,
    DARK_GRAY,
    WHITE,
    fit_font,
    format_clock,
    format_temperature,
)
from paperwhite_weather.skins.sun_arc import draw_sun_arc
from paperwhite_weather.skins.temperature_bars import (
    TemperatureRow,
    draw_temperature_bars,
    rows_for_days,
)

DESIGN_PORTRAIT = (1072, 1448)
DESIGN_LANDSCAPE = (1448, 1072)


class Canvas:
    """One frame being drawn, with the snapshot and settings it draws from."""

    def __init__(
        self, size: tuple[int, int], snapshot: WeatherSnapshot, settings: Settings, now: datetime
    ) -> None:
        self.image = Image.new("L", size, WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.width, self.height = size
        self.snapshot = snapshot
        self.settings = settings
        self.now = now
        self.tz = snapshot.location.tzinfo
        self.time_format = settings.display.time_format
        self.landscape = self.width > self.height
        design = DESIGN_LANDSCAPE if self.landscape else DESIGN_PORTRAIT
        self.scale = min(self.width / design[0], self.height / design[1])
        self.margin = round(0.06 * min(self.width, self.height))

    # Measurements

    def px(self, design_px: float) -> int:
        """Scale a design measurement to canvas pixels, never below one pixel."""
        return max(1, round(design_px * self.scale))

    @property
    def content_width(self) -> int:
        return self.width - 2 * self.margin

    # Text

    def text(
        self,
        xy: tuple[float, float],
        text: str,
        weight: Weight,
        size: float,
        fill: int = BLACK,
        anchor: str = "la",
        max_width: float | None = None,
    ) -> int:
        """Draw ``text`` at design size ``size``; shrink to ``max_width`` if given.

        Returns the font size actually used, in pixels.
        """
        if max_width is None:
            font = load_font(weight, self.px(size))
        else:
            font = fit_font(self.draw, text, weight, self.px(size), max_width)
        self.draw.text(xy, text, font=font, fill=fill, anchor=anchor)
        return int(font.size)

    def text_width(self, text: str, weight: Weight, size: float) -> float:
        return float(self.draw.textlength(text, font=load_font(weight, self.px(size))))

    def rule(
        self, x: float, y: float, width: float, fill: int = BLACK, thickness: float = 3
    ) -> int:
        self.draw.line([(x, y), (x + width, y)], fill=fill, width=self.px(thickness))
        return round(y + self.px(thickness))

    @property
    def night(self) -> bool:
        """Whether ``now`` is between sunset and the next sunrise (icons show a moon)."""
        return not (self.snapshot.sun.sunrise <= self.now <= self.snapshot.sun.sunset)

    def icon(
        self, condition: Condition, box: tuple[float, float, float, float], night: bool = False
    ) -> None:
        """Draw the condition icon in ``box``; ``night`` selects the moon variants."""
        left, top, right, bottom = (round(v) for v in box)
        draw_icon(self.draw, condition, (left, top, right, bottom), night=night)

    def sun_arc(self, box: tuple[float, float, float, float]) -> int:
        """Draw the day's sun arc (dawn to dusk, sun marked) in ``box``; returns its bottom."""
        left, top, right, bottom = (round(v) for v in box)
        draw_sun_arc(
            self.draw,
            (left, top, right, bottom),
            self.snapshot.sun,
            self.now,
            self.tz,
            self.time_format,
            self.scale,
        )
        return bottom

    def temperature_rows(
        self, days: list[DailyForecast], long_names: bool = False
    ) -> list[TemperatureRow]:
        """Bar rows for ``days``; see :func:`rows_for_days`."""
        return rows_for_days(self.snapshot, days, long_names)

    def temperature_bars(
        self,
        box: tuple[float, float, float, float],
        days: list[DailyForecast],
        long_names: bool = False,
    ) -> int:
        """Draw ``days`` as temperature bars on a shared scale in ``box``; returns its bottom."""
        left, top, right, bottom = (round(v) for v in box)
        draw_temperature_bars(
            self.draw,
            (left, top, right, bottom),
            self.temperature_rows(days, long_names),
            self.scale,
        )
        return bottom

    # Formatting shortcuts

    def clock(self, moment: datetime | None = None) -> str:
        return format_clock((moment or self.now).astimezone(self.tz), self.time_format)

    def date_line(self) -> str:
        return f"{self.now:%A}, {self.now:%B} {self.now.day}"

    def temperature(self, value: float) -> str:
        return format_temperature(value)

    def range_text(self, day: DailyForecast) -> str:
        high = format_temperature(day.temperature_high)
        return f"{high} / {format_temperature(day.temperature_low)}"

    def high_low(self, day: DailyForecast) -> str:
        """``"H 75°   L 57°"``."""
        high = format_temperature(day.temperature_high)
        return f"H {high}   L {format_temperature(day.temperature_low)}"

    def condition_label(self, condition: Condition) -> str:
        return CONDITION_LABELS[condition]

    def feels_like_text(self) -> str:
        """``"Feels like 68°"``, or an empty string when the provider has no value."""
        feels = self.snapshot.current.feels_like
        return "" if feels is None else f"Feels like {self.temperature(feels)}"

    def footer(self) -> None:
        """Data freshness and units, bottom right, so stale data is obvious."""
        snapshot = self.snapshot
        text = (
            f"Updated {self.clock(snapshot.fetched_at)}"
            f"  ·  {snapshot.source}  ·  {snapshot.units.temperature_symbol}"
        )
        self.text(
            (self.width - self.margin, self.height - self.margin),
            text,
            "regular",
            28,
            fill=DARK_GRAY,
            anchor="rd",
        )

    def metrics(self) -> list[tuple[str, str]]:
        """Optional current-conditions values that are present, as (label, value)."""
        current = self.snapshot.current
        units = self.snapshot.units
        wind_unit = {"kmh": "km/h", "mph": "mph", "ms": "m/s"}[units.wind]
        rows: list[tuple[str, str]] = []
        if current.feels_like is not None:
            rows.append(("Feels like", self.temperature(current.feels_like)))
        if current.humidity_percent is not None:
            rows.append(("Humidity", f"{round(current.humidity_percent)}%"))
        if current.wind_speed is not None:
            rows.append(("Wind", f"{round(current.wind_speed)} {wind_unit}"))
        if current.precipitation_probability is not None:
            rows.append(("Precipitation", f"{round(current.precipitation_probability)}%"))
        return rows
