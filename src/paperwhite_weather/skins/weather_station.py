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
    """Clock, current conditions, a metrics grid, the sun arc, and the forecast."""

    name: ClassVar[str] = "weather-station"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        m = c.margin
        w = c.content_width

        # Header: clock left, date right.
        c.text((m, m), c.clock(), "bold", 96, anchor="la", max_width=w * 0.5)
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
            gy = self._grid(c, right_x, y, right_w)
            ay = c.sun_arc((m, self._current_height(c, y), m + left_w, y + c.px(420)))
            y2 = max(ay, gy) + c.px(30)
            y2 = c.rule(m, y2, w, LIGHT_GRAY, 2) + c.px(24)
            self._forecast_columns(c, m, y2, w)
        else:
            self._current(c, m, y, w)
            y = self._current_height(c, y) + c.px(20)
            y = self._grid(c, m, y, w) + c.px(30)
            y = c.sun_arc((m, y, c.width - m, y + c.px(270))) + c.px(30)
            y = c.rule(m, y, w, LIGHT_GRAY, 2) + c.px(24)
            self._forecast_columns(c, m, y, w)
        c.footer()
        return c.image

    # Blocks

    def _current(self, c: Canvas, x: int, y: int, width: int) -> None:
        icon = c.px(200)
        c.icon(c.snapshot.current.condition, (x, y, x + icon, y + icon))
        tx = x + icon + c.px(30)
        temp = c.temperature(c.snapshot.current.temperature)
        c.text(
            (tx, y - c.px(16)), temp, "bold", 170, anchor="la", max_width=width - icon - c.px(30)
        )
        today = c.snapshot.today
        c.text(
            (tx, y + c.px(150)),
            c.condition_label(c.snapshot.current.condition),
            "regular",
            44,
            anchor="la",
            max_width=width - icon - c.px(30),
        )
        c.text(
            (tx, y + c.px(205)),
            c.high_low(today),
            "regular",
            40,
            fill=DARK_GRAY,
            anchor="la",
            max_width=width - icon - c.px(30),
        )

    def _current_height(self, c: Canvas, y: int) -> int:
        return y + c.px(260)

    def _grid(self, c: Canvas, x: int, y: int, width: int) -> int:
        """Two columns of label/value cells with the optional metrics. Returns the bottom y."""
        cells = c.metrics()
        columns = 2
        cell_w = width / columns
        cell_h = c.px(96)
        for k, (label, value) in enumerate(cells):
            cx = x + cell_w * (k % columns)
            cy = y + cell_h * (k // columns)
            c.text((cx, cy), label, "regular", 30, fill=DARK_GRAY, anchor="la")
            c.text((cx, cy + c.px(34)), value, "bold", 46, anchor="la", max_width=cell_w * 0.95)
        rows = (len(cells) + columns - 1) // columns
        return round(y + cell_h * rows)

    def _forecast_columns(self, c: Canvas, x: int, y: int, width: int) -> None:
        days = c.snapshot.daily[1 : _FORECAST_DAYS + 1]
        if not days:
            return
        column = width / len(days)
        icon = c.px(110)
        for k, day in enumerate(days):
            cx = x + column * (k + 0.5)
            c.text((cx, y), f"{day.date:%a}", "bold", 40, anchor="ma")
            c.icon(day.condition, (cx - icon / 2, y + c.px(52), cx + icon / 2, y + c.px(52) + icon))
            c.text(
                (cx, y + c.px(52) + icon + c.px(14)),
                c.range_text(day),
                "regular",
                36,
                anchor="ma",
                max_width=column * 0.95,
            )
            if day.precipitation_probability is not None:
                c.text(
                    (cx, y + c.px(52) + icon + c.px(62)),
                    f"{round(day.precipitation_probability)}%",
                    "regular",
                    30,
                    fill=DARK_GRAY,
                    anchor="ma",
                )
