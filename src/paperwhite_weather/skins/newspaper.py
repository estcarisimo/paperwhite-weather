"""Newspaper skin: a typographic front page in a serif face."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.skins.base import BLACK
from paperwhite_weather.skins.common import Canvas

_FORECAST_DAYS = 4


class NewspaperSkin:
    """Masthead, dateline, a lead story on the conditions, and the forecast below the fold."""

    name: ClassVar[str] = "newspaper"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        m = c.margin
        w = c.content_width
        name = snapshot.location.name or "The Weather"

        # Masthead.
        y = m
        c.text((c.width / 2, y), name.upper(), "serif-bold", 96, anchor="ma", max_width=w)
        y += c.px(120)
        y = c.rule(m, y, w, BLACK, 4) + c.px(8)
        c.text(
            (m, y),
            f"{now:%A}, {now:%B} {now.day}, {now:%Y}",
            "serif",
            32,
            anchor="la",
            max_width=w * 0.6,
        )
        c.text((c.width - m, y), c.clock(), "serif", 32, anchor="ra")
        y += c.px(48)
        y = c.rule(m, y, w, BLACK, 2) + c.px(36)

        # Lead story: text column on the left, the icon on the right.
        current = snapshot.current
        today = snapshot.today
        icon = c.px(280 if c.landscape else 240)
        text_w = w - icon - c.px(40)
        lead_top = y
        headline = f"{c.condition_label(current.condition)}, {c.temperature(current.temperature)}"
        headline_size = 100 if c.landscape else 84
        used = c.text((m, y), headline, "serif-bold", headline_size, anchor="la", max_width=text_w)
        y += round(used * 1.3)
        low = c.temperature(today.temperature_low)
        deck = f"High {c.temperature(today.temperature_high)}, low {low}."
        if today.precipitation_probability is not None:
            deck += f" Chance of precipitation {round(today.precipitation_probability)}%."
        extras = [
            f"{label.lower()} {value}" for label, value in c.metrics() if label != "Precipitation"
        ]
        if extras:
            deck += " Currently " + ", ".join(extras) + "."
        y = self._paragraph(c, m, y, text_w, deck, 38)
        sun = snapshot.sun
        y = self._paragraph(
            c,
            m,
            y + c.px(10),
            text_w,
            f"Civil dawn {c.clock(sun.civil_dawn)}, sunrise {c.clock(sun.sunrise)}, "
            f"sunset {c.clock(sun.sunset)}, civil dusk {c.clock(sun.civil_dusk)}.",
            34,
        )
        c.icon(current.condition, (c.width - m - icon, lead_top, c.width - m, lead_top + icon))
        y = max(y, lead_top + icon)

        # Below the fold: the forecast as columns, sized to the space that is left.
        y += c.px(30)
        y = c.rule(m, y, w, BLACK, 2) + c.px(20)
        c.text((m, y), "The days ahead", "serif-bold", 40, anchor="la")
        y += c.px(60)
        days = snapshot.daily[1 : _FORECAST_DAYS + 1]
        if days:
            available = c.height - m - c.px(50) - y  # leave room for the footer
            small = max(c.px(60), min(c.px(120), available - c.px(110)))
            column = w / len(days)
            for k, day in enumerate(days):
                x = m + column * k
                c.text(
                    (x, y), f"{day.date:%A}", "serif-bold", 34, anchor="la", max_width=column * 0.95
                )
                c.icon(day.condition, (x, y + c.px(46), x + small, y + c.px(46) + small))
                c.text(
                    (x, y + c.px(46) + small + c.px(10)),
                    f"{c.range_text(day)}  {c.condition_label(day.condition)}",
                    "serif",
                    30,
                    anchor="la",
                    max_width=column * 0.95,
                )
        c.footer()
        return c.image

    def _paragraph(self, c: Canvas, x: int, y: int, width: int, text: str, size: float) -> int:
        """Word-wrap ``text`` into lines no wider than ``width``. Returns the bottom y."""
        from paperwhite_weather.fonts import load_font

        font = load_font("serif", c.px(size))
        words = text.split()
        lines: list[str] = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if c.draw.textlength(candidate, font=font) <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        for text_line in lines:
            c.draw.text((x, y), text_line, font=font, fill=BLACK, anchor="la")
            y += round(font.size * 1.35)
        return y
