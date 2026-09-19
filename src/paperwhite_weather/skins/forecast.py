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

        # Today: icon, temperature, condition, range, precipitation.
        y += c.px(30)
        icon_size = c.px(230)
        c.icon(snapshot.current.condition, (m, y, m + icon_size, y + icon_size))
        x = m + icon_size + c.px(40)
        temp = c.temperature(snapshot.current.temperature)
        c.text((x, y - c.px(20)), temp, "bold", 200, anchor="la", max_width=w * 0.45)
        x2 = x + c.text_width(temp, "bold", 200) + c.px(30)
        today = snapshot.today
        lines = [
            (c.condition_label(snapshot.current.condition), 52, BLACK),
            (
                c.high_low(today),
                44,
                DARK_GRAY,
            ),
        ]
        if today.precipitation_probability is not None:
            lines.append(
                (f"Precipitation {round(today.precipitation_probability)}%", 40, DARK_GRAY)
            )
        ly = y + c.px(20)
        for text, size_, fill in lines:
            used = c.text(
                (x2, ly), text, "regular", size_, fill=fill, anchor="la", max_width=c.width - m - x2
            )
            ly += round(used * 1.4)
        y += icon_size + c.px(40)
        y = c.rule(m, y, w, LIGHT_GRAY, 2)
        y += c.px(30)

        # Forecast: every day including today, as columns (portrait) or rows (landscape).
        days = snapshot.daily[:_MAX_DAYS]
        if c.landscape:
            column = w / len(days)
            icon = c.px(150)
            for k, day in enumerate(days):
                cx = m + column * (k + 0.5)
                label = "Today" if k == 0 else f"{day.date:%a}"
                c.text((cx, y), label, "bold", 44, anchor="ma")
                c.icon(
                    day.condition, (cx - icon / 2, y + c.px(60), cx + icon / 2, y + c.px(60) + icon)
                )
                c.text(
                    (cx, y + c.px(60) + icon + c.px(20)),
                    c.range_text(day),
                    "regular",
                    40,
                    anchor="ma",
                    max_width=column * 0.95,
                )
                if day.precipitation_probability is not None:
                    c.text(
                        (cx, y + c.px(60) + icon + c.px(75)),
                        f"{round(day.precipitation_probability)}%",
                        "regular",
                        34,
                        fill=DARK_GRAY,
                        anchor="ma",
                    )
        else:
            row = (c.height - m - c.px(60) - y) / len(days)
            icon = min(c.px(120), round(row * 0.8))
            for k, day in enumerate(days):
                top = y + row * k
                cy = top + row / 2
                label = "Today" if k == 0 else f"{day.date:%A}"
                c.text((m, cy), label, "bold", 46, anchor="lm", max_width=w * 0.34)
                c.icon(
                    day.condition, (m + w * 0.38, cy - icon / 2, m + w * 0.38 + icon, cy + icon / 2)
                )
                c.text((c.width - m, cy - c.px(14)), c.range_text(day), "regular", 46, anchor="rm")
                if day.precipitation_probability is not None:
                    c.text(
                        (c.width - m, cy + c.px(36)),
                        f"{round(day.precipitation_probability)}%",
                        "regular",
                        32,
                        fill=DARK_GRAY,
                        anchor="rm",
                    )
                if k:
                    c.rule(m, top, w, LIGHT_GRAY, 1)
        c.footer()
        return c.image
