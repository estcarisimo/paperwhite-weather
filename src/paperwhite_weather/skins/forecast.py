"""Forecast skin: today's conditions plus a large multi-day forecast; the clock is small."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, LIGHT_GRAY
from paperwhite_weather.skins.common import Canvas

_MAX_DAYS = 5


class ForecastSkin:
    """The week at a glance."""

    name: ClassVar[str] = "forecast"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        m = c.margin
        w = c.content_width

        # Header: date left, small clock right.
        c.text((m, m), c.date_line(), "bold", 44, anchor="la", max_width=w * 0.65)
        c.text((c.width - m, m), c.clock(), "regular", 44, fill=DARK_GRAY, anchor="ra")
        y = m + c.px(70)
        y = c.rule(m, y, w, BLACK, 3)

        # Today: icon, temperature, condition, range, precipitation; the sun arc to the
        # right in landscape, below in portrait.
        y += c.px(30)
        icon_size = c.px(200 if c.landscape else 230)
        temp_size = 170 if c.landscape else 200
        c.icon(snapshot.current.condition, (m, y, m + icon_size, y + icon_size), night=c.night)
        x = m + icon_size + c.px(40)
        temp = c.temperature(snapshot.current.temperature)
        c.text((x, y - c.px(20)), temp, "bold", temp_size, anchor="la", max_width=w * 0.45)
        x2 = x + c.text_width(temp, "bold", temp_size) + c.px(30)
        lines = [
            (c.condition_label(snapshot.current.condition), 46 if c.landscape else 52, BLACK),
            (c.feels_like_text(), 40 if c.landscape else 44, DARK_GRAY),
        ]
        arc_left = c.width - m - c.px(430)
        text_right = arc_left - c.px(30) if c.landscape else c.width - m
        ly = y + c.px(20)
        for text, size_, fill in lines:
            used = c.text(
                (x2, ly), text, "regular", size_, fill=fill, anchor="la", max_width=text_right - x2
            )
            ly += round(used * 1.4)
        if c.landscape:
            c.sun_arc((arc_left, y - c.px(10), c.width - m, y + icon_size + c.px(10)))
            y += icon_size + c.px(40)
        else:
            y += icon_size + c.px(30)
            y = c.sun_arc((m, y, c.width - m, y + c.px(230))) + c.px(30)
        y = c.rule(m, y, w, LIGHT_GRAY, 2)
        y += c.px(30)

        # Forecast: every day including today as temperature bars on one scale.
        days = snapshot.daily[:_MAX_DAYS]
        c.temperature_bars(
            (m, y, c.width - m, c.height - m - c.px(50)), days, long_names=not c.landscape
        )
        c.footer()
        return c.image
