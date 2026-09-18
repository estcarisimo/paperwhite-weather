"""Minimal skin: a large clock and temperature, today's range, sun times, a compact forecast.

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
from paperwhite_weather.models import DailyForecast, SunTimes, WeatherSnapshot
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
        y = self.sun_line(x, y + self.px(20), content_width)
        y = self.rule(x, y + self.px(30), content_width, LIGHT_GRAY, 2)
        self.forecast_columns(x, y + self.px(40), content_width)
        self.footer()

    def compose_landscape(self) -> None:
        gutter = self.px(60)
        left_width = round((self.width - 2 * self.margin - gutter) * 0.56)
        right_x = self.margin + left_width + gutter
        right_width = self.width - self.margin - right_x

        y = self.margin
        y = self.masthead(self.margin, y, left_width, clock_size=250)
        y = self.rule(self.margin, y, left_width, BLACK, 4)
        self.lead(self.margin, y + self.px(50), left_width)

        y = self.margin
        y = self.sun_block(right_x, y, right_width)
        y = self.rule(right_x, y + self.px(30), right_width, LIGHT_GRAY, 2)
        self.forecast_rows(right_x, y + self.px(30), right_width)
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
        """Current temperature with conditions and today's range beside it."""
        current = self.snapshot.current
        today = self.snapshot.today
        temperature = format_temperature(current.temperature)
        font = fit_font(self.draw, temperature, "bold", self.px(210), width * 0.5)
        self.draw.text((x, y), temperature, font=font, fill=BLACK, anchor="la")
        detail_x = x + round(self.draw.textlength(temperature, font=font)) + self.px(30)
        detail_width = x + width - detail_x
        lines = [
            (CONDITION_LABELS[current.condition], 56, BLACK),
            (
                f"H {format_temperature(today.temperature_high)}   "
                f"L {format_temperature(today.temperature_low)}",
                48,
                DARK_GRAY,
            ),
        ]
        if today.precipitation_probability is not None:
            lines.append(
                (f"Precipitation {round(today.precipitation_probability)}%", 40, DARK_GRAY)
            )
        line_y = y + self.px(30)
        for text, size, fill in lines:
            line_font = fit_font(self.draw, text, "regular", self.px(size), detail_width)
            self.draw.text((detail_x, line_y), text, font=line_font, fill=fill, anchor="la")
            line_y += round(line_font.size * 1.4)
        return max(y + round(font.size * 1.3), line_y)

    def sun_events(self) -> list[tuple[str, str]]:
        sun: SunTimes = self.snapshot.sun
        return [
            (label, format_clock(moment.astimezone(self.tz), self.time_format))
            for label, moment in (
                ("Dawn", sun.civil_dawn),
                ("Sunrise", sun.sunrise),
                ("Sunset", sun.sunset),
                ("Dusk", sun.civil_dusk),
            )
        ]

    def sun_line(self, x: int, y: int, width: int) -> int:
        """All four sun events on one line (portrait)."""
        text = "   ".join(f"{label} {clock}" for label, clock in self.sun_events())
        font = fit_font(self.draw, text, "regular", self.px(34), width)
        self.draw.text((x, y), text, font=font, fill=BLACK, anchor="la")
        return y + round(font.size * 1.5)

    def sun_block(self, x: int, y: int, width: int) -> int:
        """Sun events as a two-by-two grid (landscape)."""
        self.draw.text((x, y), "Sun", font=load_font("bold", self.px(40)), fill=BLACK, anchor="la")
        y += self.px(60)
        column = width / 2
        label_font = load_font("regular", self.px(30))
        value_font = load_font("bold", self.px(44))
        for index, (label, clock) in enumerate(self.sun_events()):
            cell_x = x + round(column * (index % 2))
            cell_y = y + self.px(105) * (index // 2)
            self.draw.text((cell_x, cell_y), label, font=label_font, fill=DARK_GRAY, anchor="la")
            self.draw.text(
                (cell_x, cell_y + self.px(34)), clock, font=value_font, fill=BLACK, anchor="la"
            )
        return y + self.px(105) * 2

    def upcoming(self) -> list[DailyForecast]:
        return self.snapshot.daily[1 : _FORECAST_DAYS + 1]

    def forecast_columns(self, x: int, y: int, width: int) -> int:
        """Next days side by side (portrait)."""
        days = self.upcoming()
        if not days:
            return y
        column = width / len(days)
        for index, day in enumerate(days):
            center = x + column * (index + 0.5)
            self.draw.text(
                (center, y),
                f"{day.date:%a}",
                font=load_font("bold", self.px(40)),
                fill=BLACK,
                anchor="ma",
            )
            self.draw.text(
                (center, y + self.px(55)),
                CONDITION_LABELS[day.condition],
                font=fit_font(
                    self.draw,
                    CONDITION_LABELS[day.condition],
                    "regular",
                    self.px(28),
                    column * 0.95,
                ),
                fill=DARK_GRAY,
                anchor="ma",
            )
            self.draw.text(
                (center, y + self.px(100)),
                _temperature_range(day),
                font=load_font("regular", self.px(36)),
                fill=BLACK,
                anchor="ma",
            )
        return y + self.px(150)

    def forecast_rows(self, x: int, y: int, width: int) -> int:
        """Next days as rows: weekday, condition, high / low (landscape)."""
        row_height = self.px(96)
        day_font = load_font("bold", self.px(40))
        range_font = load_font("regular", self.px(40))
        for day in self.upcoming():
            self.draw.text((x, y), f"{day.date:%a}", font=day_font, fill=BLACK, anchor="la")
            condition = CONDITION_LABELS[day.condition]
            self.draw.text(
                (x + self.px(110), y + self.px(6)),
                condition,
                font=fit_font(self.draw, condition, "regular", self.px(32), width * 0.45),
                fill=DARK_GRAY,
                anchor="la",
            )
            self.draw.text(
                (x + width, y),
                _temperature_range(day),
                font=range_font,
                fill=BLACK,
                anchor="ra",
            )
            y += row_height
        return y

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


def _temperature_range(day: DailyForecast) -> str:
    return f"{format_temperature(day.temperature_high)} / {format_temperature(day.temperature_low)}"
