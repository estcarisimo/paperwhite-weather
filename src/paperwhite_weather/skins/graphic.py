"""Graphic skin: the picture end of the range.

A hero of the current condition (a large icon and the temperature in the display face),
the optional metrics as glyphs, the sun arc, and the week as a high/low band chart.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import DailyForecast, WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, PALE_GRAY
from paperwhite_weather.skins.common import Canvas

_MAX_DAYS = 5


class GraphicSkin:
    """Fewer words, more pictures: icon, numerals, arc, and a band chart."""

    name: ClassVar[str] = "graphic"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        m = c.margin
        w = c.content_width
        c.text((m, m), c.date_line(), "medium", 44, fill=DARK_GRAY, anchor="la", max_width=w * 0.6)
        c.number(c.width - m, m - c.px(4), c.clock(), 76, w * 0.35)
        y = c.rule(m, m + c.px(96), w, BLACK, 4)
        days = snapshot.daily[:_MAX_DAYS]
        if c.landscape:
            self._landscape(c, y, days)
        else:
            self._portrait(c, y, days)
        c.footer()
        return c.image

    def _portrait(self, c: Canvas, y: int, days: list[DailyForecast]) -> None:
        m = c.margin
        w = c.content_width
        y += c.px(36)
        y = self._hero(c, m, y, w, icon_size=260, number_size=280, label_size=52)
        y = c.metrics_strip((m, y + c.px(30), c.width - m, y + c.px(200))) + c.px(10)
        y = c.sun_arc((m, y, c.width - m, y + c.px(200))) + c.px(20)
        y = c.rule(m, y, w, PALE_GRAY, 3) + c.px(16)
        c.band_chart((m, y, c.width - m, c.height - m - c.px(50)), days)

    def _landscape(self, c: Canvas, y: int, days: list[DailyForecast]) -> None:
        m = c.margin
        column = round(c.content_width * 0.40)
        y += c.px(30)
        hero_bottom = self._hero(c, m, y, column, icon_size=220, number_size=250, label_size=46)
        strip_bottom = c.metrics_strip(
            (m, hero_bottom + c.px(34), m + column, hero_bottom + c.px(200)), compact=True
        )
        c.sun_arc((m, strip_bottom + c.px(24), m + column, c.height - m - c.px(20)))
        x = m + column + c.px(70)
        c.draw.line([(x - c.px(35), y), (x - c.px(35), c.height - m)], fill=PALE_GRAY, width=3)
        c.band_chart((x, y - c.px(10), c.width - m, c.height - m - c.px(50)), days)

    def _hero(
        self,
        c: Canvas,
        x: int,
        y: int,
        width: int,
        icon_size: int,
        number_size: int,
        label_size: int,
    ) -> int:
        """Large icon on the left, the temperature on the right, the condition under it."""
        current = c.snapshot.current
        icon = c.px(icon_size)
        c.icon(current.condition, (x, y, x + icon, y + icon), night=c.night)
        bottom = c.number(
            x + width + c.px(8),
            y - c.px(10),
            c.temperature(current.temperature),
            number_size,
            width - icon - c.px(40),
        )
        c.text(
            (x + width, bottom + c.px(24)),
            c.condition_label(current.condition),
            "medium",
            label_size,
            anchor="ra",
            max_width=width - icon - c.px(40),
        )
        return max(y + icon, bottom + c.px(24) + c.px(label_size) + c.px(8))
