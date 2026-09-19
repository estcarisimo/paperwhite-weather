"""Minimal skin: a large clock and temperature, today's range, the sun arc, a compact forecast.

Two layouts share the same building blocks: a single column in portrait and two columns in
landscape, so the landscape frame uses the full width instead of being a scaled-down
portrait page.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image, ImageDraw

from paperwhite_weather.config import Settings
from paperwhite_weather.fonts import load_font
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.skins.base import (
    BLACK,
    CONDITION_LABELS,
    DARK_GRAY,
    LIGHT_GRAY,
    WHITE,
    fit_font,
    format_clock,
    format_temperature,
)
from paperwhite_weather.skins.sun_arc import draw_sun_arc
from paperwhite_weather.skins.temperature_bars import TemperatureRow, draw_temperature_bars

#: The layout is designed for the Paperwhite 3 canvas (1072x1448 portrait, 1448x1072
#: landscape) and scaled down uniformly when the actual canvas is smaller.
_DESIGN_PORTRAIT = (1072, 1448)
_DESIGN_LANDSCAPE = (1448, 1072)
_FORECAST_DAYS = 4


class MinimalSkin:
    """Large typography, no icons yet, readable from across a room."""

    name: ClassVar[str] = "minimal"

    def compose(
        self,
        snapshot: WeatherSnapshot,
        settings: Settings,
        now: datetime,
        size: tuple[int, int],
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        width, height = size
        image = Image.new("L", size, WHITE)
        frame = _Frame(image, snapshot, settings, now)
        if width > height:
            frame.compose_landscape()
        else:
            frame.compose_portrait()
        return image


class _Frame:
    """One frame being drawn; holds the shared state the layout helpers need."""

    def __init__(
        self,
        image: Image.Image,
        snapshot: WeatherSnapshot,
        settings: Settings,
        now: datetime,
    ) -> None:
        self.draw = ImageDraw.Draw(image)
        self.width, self.height = image.size
        self.snapshot = snapshot
        self.now = now
        self.tz = snapshot.location.tzinfo
        self.time_format = settings.display.time_format
        design = _DESIGN_LANDSCAPE if self.width > self.height else _DESIGN_PORTRAIT
        self.scale = min(self.width / design[0], self.height / design[1])
        self.margin = round(0.06 * min(self.width, self.height))

    def px(self, design_px: float) -> int:
        """Scale a design measurement to canvas pixels, never below one pixel."""
        return max(1, round(design_px * self.scale))

    # Layouts

    def compose_portrait(self) -> None:
        x = self.margin
        content_width = self.width - 2 * self.margin
        y = self.margin
        y = self.masthead(x, y, content_width, clock_size=230)
        y = self.rule(x, y, content_width, BLACK, 4)
        y = self.lead(x, y + self.px(40), content_width)
        y = self.sun_arc(x, y + self.px(30), content_width, self.px(250))
        y = self.rule(x, y + self.px(30), content_width, LIGHT_GRAY, 2)
        self.temperature_bars(x, y + self.px(24), content_width, long_names=True)
        self.footer()

    def compose_landscape(self) -> None:
        gutter = self.px(60)
        left_width = round((self.width - 2 * self.margin - gutter) * 0.45)
        right_x = self.margin + left_width + gutter
        right_width = self.width - self.margin - right_x

        y = self.margin
        y = self.masthead(self.margin, y, left_width, clock_size=250)
        y = self.rule(self.margin, y, left_width, BLACK, 4)
        y = self.lead(self.margin, y + self.px(50), left_width)
        self.sun_arc(self.margin, y + self.px(70), left_width, self.px(300))

        self.temperature_bars(right_x, self.margin + self.px(10), right_width)
        self.footer()

    # Building blocks; each returns the y coordinate below what it drew.

    def masthead(self, x: int, y: int, width: int, clock_size: int) -> int:
        self.draw.text(
            (x, y),
            f"{self.now:%A}, {self.now:%B} {self.now.day}",
            font=load_font("bold", self.px(46)),
            fill=BLACK,
            anchor="la",
        )
        y += self.px(70)
        clock = format_clock(self.now, self.time_format)
        font = fit_font(self.draw, clock, "bold", self.px(clock_size), width)
        self.draw.text((x, y), clock, font=font, fill=BLACK, anchor="la")
        return y + round(font.size * 1.25)

    def rule(self, x: int, y: int, width: int, fill: int, thickness: int) -> int:
        self.draw.line([(x, y), (x + width, y)], fill=fill, width=self.px(thickness))
        return y + self.px(thickness)

    def lead(self, x: int, y: int, width: int) -> int:
        """Current temperature with the condition and feels-like beside it."""
        current = self.snapshot.current
        temperature = format_temperature(current.temperature)
        font = fit_font(self.draw, temperature, "bold", self.px(210), width * 0.5)
        self.draw.text((x, y), temperature, font=font, fill=BLACK, anchor="la")
        detail_x = x + round(self.draw.textlength(temperature, font=font)) + self.px(30)
        detail_width = x + width - detail_x
        lines = [(CONDITION_LABELS[current.condition], 56, BLACK)]
        if current.feels_like is not None:
            lines.append((f"Feels like {format_temperature(current.feels_like)}", 48, DARK_GRAY))
        line_y = y + self.px(30)
        for text, size, fill in lines:
            line_font = fit_font(self.draw, text, "regular", self.px(size), detail_width)
            self.draw.text((detail_x, line_y), text, font=line_font, fill=fill, anchor="la")
            line_y += round(line_font.size * 1.4)
        return max(y + round(font.size * 1.3), line_y)

    def sun_arc(self, x: int, y: int, width: int, height: int) -> int:
        """The day's sun arc: dawn to dusk, sun marked, sunrise and sunset labeled."""
        draw_sun_arc(
            self.draw,
            (x, y, x + width, y + height),
            self.snapshot.sun,
            self.now,
            self.tz,
            self.time_format,
            self.scale,
        )
        return y + height

    def temperature_bars(self, x: int, y: int, width: int, long_names: bool = False) -> int:
        """Today and the next days as bars on one scale, down to the footer."""
        days = self.snapshot.daily[: _FORECAST_DAYS + 1]
        today = self.snapshot.today.date
        rows = []
        for day in days:
            is_today = day.date == today
            label = "Today" if is_today else f"{day.date:%A}" if long_names else f"{day.date:%a}"
            note = None
            if day.precipitation_probability is not None:
                note = f"{round(day.precipitation_probability)}%"
            rows.append(
                TemperatureRow(
                    label,
                    day.temperature_low,
                    day.temperature_high,
                    day.condition,
                    self.snapshot.current.temperature if is_today else None,
                    note,
                )
            )
        bottom = self.height - self.margin - self.px(50)
        draw_temperature_bars(self.draw, (x, y, x + width, bottom), rows, self.scale)
        return bottom

    def footer(self) -> None:
        """Data freshness and units, bottom right, so stale data is obvious."""
        snapshot = self.snapshot
        text = (
            f"Updated {format_clock(snapshot.fetched_at.astimezone(self.tz), self.time_format)}"
            f"  ·  {snapshot.source}  ·  {snapshot.units.temperature_symbol}"
        )
        self.draw.text(
            (self.width - self.margin, self.height - self.margin),
            text,
            font=load_font("regular", self.px(28)),
            fill=DARK_GRAY,
            anchor="rd",
        )
