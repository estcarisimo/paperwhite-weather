"""Weather-station skin: dense; every value the data model carries."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, LIGHT_GRAY
from paperwhite_weather.skins.common import Canvas

_FORECAST_DAYS = 4


class WeatherStationSkin:
    """Clock, current conditions, every metric as a glyph (UV and the moon included), the
    sun arc, and the forecast."""

    name: ClassVar[str] = "weather-station"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        m = c.margin
        w = c.content_width

        # Header: clock left, date right.
        c.stamped_clock(m, m, "bold", 96, max_width=w * 0.55)
        c.text(
            (c.width - m, m + c.px(30)),
            c.date_line(),
            "regular",
            40,
            fill=DARK_GRAY,
            anchor="ra",
            max_width=w * 0.48,
        )
        y = m + c.px(120)
        y = c.rule(m, y, w, BLACK, 3) + c.px(24)

        if c.landscape:
            gutter = c.px(50)
            left_w = round((w - gutter) * 0.5)
            right_x = m + left_w + gutter
            right_w = c.width - m - right_x
            self._current(c, m, y, left_w)
            gy = c.metrics_strip(
                (right_x, y + c.px(10), right_x + right_w, y + c.px(300)), extras=True
            )
            ay = c.sun_arc((m, self._current_height(c, y), m + left_w, y + c.px(430)))
            y2 = max(ay, gy) + c.px(30)
            y2 = c.rule(m, y2, w, LIGHT_GRAY, 2) + c.px(16)
            self._forecast(c, m, y2, w)
        else:
            self._current(c, m, y, w)
            y = self._current_height(c, y) + c.px(20)
            y = c.metrics_strip((m, y, c.width - m, y + c.px(300)), extras=True) + c.px(30)
            y = c.sun_arc((m, y, c.width - m, y + c.px(270))) + c.px(30)
            y = c.rule(m, y, w, LIGHT_GRAY, 2) + c.px(16)
            self._forecast(c, m, y, w)
        c.footer()
        return c.image

    # Blocks

    def _current(self, c: Canvas, x: int, y: int, width: int) -> None:
        icon = c.px(200)
        c.icon(c.snapshot.current.condition, (x, y, x + icon, y + icon), night=c.night)
        tx = x + icon + c.px(30)
        temp = c.temperature(c.snapshot.current.temperature)
        c.text(
            (tx, y - c.px(16)), temp, "bold", 170, anchor="la", max_width=width - icon - c.px(30)
        )
        c.text(
            (tx, y + c.px(150)),
            c.condition_label(c.snapshot.current.condition),
            "regular",
            44,
            anchor="la",
            max_width=width - icon - c.px(30),
        )

    def _current_height(self, c: Canvas, y: int) -> int:
        return y + c.px(215)

    def _forecast(self, c: Canvas, x: int, y: int, width: int) -> None:
        """Today and the next days as temperature bars on one scale, down to the footer."""
        days = c.snapshot.daily[: _FORECAST_DAYS + 1]
        c.temperature_bars((x, y, x + width, c.height - c.margin - c.px(50)), days)
