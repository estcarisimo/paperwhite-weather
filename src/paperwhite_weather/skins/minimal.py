"""Minimal skin: the quiet end of the range.

Date, a large clock, the current temperature with its icon and condition, today's range,
the sun arc, and four days as columns. Portrait stacks them; landscape puts the clock,
the temperature, and the arc in a left column and the four days in a right column.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import DailyForecast, WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, PALE_GRAY
from paperwhite_weather.skins.common import Canvas

_FORECAST_DAYS = 4


class MinimalSkin:
    """Large typography and one graphic, readable from across a room."""

    name: ClassVar[str] = "minimal"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        if c.landscape:
            self._landscape(c)
        else:
            self._portrait(c)
        c.footer()
        return c.image

    def _portrait(self, c: Canvas) -> None:
        m = c.margin
        w = c.content_width
        y = self._masthead(c, m, m, w, clock_size=220)
        y = self._today(c, m, y + c.px(40), w, icon_size=250, temperature_size=250, wide=True)
        y = c.sun_arc((m, y + c.px(24), c.width - m, y + c.px(24) + c.px(200)))
        y = c.rule(m, y + c.px(36), w, PALE_GRAY, 3) + c.px(30)
        c.day_columns((m, y, c.width - m, c.height - m - c.px(40)), self._days(c))

    def _landscape(self, c: Canvas) -> None:
        m = c.margin
        gutter = c.px(60)
        column = round((c.content_width - gutter) * 0.5)
        y = self._masthead(c, m, m, column, clock_size=190)
        y = self._today(c, m, y + c.px(40), column, icon_size=210, temperature_size=210)
        c.sun_arc((m, y + c.px(20), m + column, c.height - m - c.px(20)))
        x = m + column + gutter
        c.day_columns((x, m + c.px(10), c.width - m, c.height - m - c.px(50)), self._days(c))

    # Blocks; each returns the y below what it drew.

    def _masthead(self, c: Canvas, x: int, y: int, width: int, clock_size: int) -> int:
        c.text((x, y), c.date_line(), "medium", 42, fill=DARK_GRAY, anchor="la", max_width=width)
        y += c.px(56)
        used = c.stamped_clock(x - c.px(6), y, "bold", clock_size, max_width=width)
        y += round(used * 1.18)
        return c.rule(x, y, width, BLACK, 4)

    def _today(
        self,
        c: Canvas,
        x: int,
        y: int,
        width: int,
        icon_size: int,
        temperature_size: int,
        wide: bool = False,
    ) -> int:
        """Icon, the temperature beside it, then the condition and today's range.

        The range goes on the same line as the condition, right-aligned, when ``wide``;
        otherwise on the line below.
        """
        current = c.snapshot.current
        icon = c.px(icon_size)
        c.icon(current.condition, (x, y, x + icon, y + icon), night=c.night)
        tx = x + icon + c.px(30)
        c.text(
            (tx - c.px(8), y - c.px(24)),
            c.temperature(current.temperature),
            "bold",
            temperature_size,
            anchor="la",
            max_width=width - icon - c.px(30),
        )
        line_y = y + icon + c.px(10)
        c.text(
            (tx, line_y),
            c.condition_label(current.condition),
            "regular",
            52,
            anchor="la",
            max_width=width - icon - c.px(30),
        )
        if wide:
            c.text(
                (x + width, line_y + c.px(4)),
                c.range_text(c.snapshot.today),
                "regular",
                48,
                fill=DARK_GRAY,
                anchor="ra",
            )
            return line_y + c.px(66)
        c.text(
            (tx, line_y + c.px(64)), c.range_text(c.snapshot.today), "regular", 44, fill=DARK_GRAY
        )
        return line_y + c.px(64) + c.px(58)

    def _days(self, c: Canvas) -> list[DailyForecast]:
        return c.snapshot.daily[1 : _FORECAST_DAYS + 1]
