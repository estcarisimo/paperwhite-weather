"""Timeline skin: the day's progression hour by hour."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.fonts import load_font
from paperwhite_weather.icons import draw_drop
from paperwhite_weather.models import HourlyForecast, WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, PALE_GRAY
from paperwhite_weather.skins.common import Canvas
from paperwhite_weather.skins.timeline_chart import draw_timeline, hours_from_midnight

_PORTRAIT_HOURS = 25  # midnight to midnight, both ends labeled
_LANDSCAPE_HOURS = 36  # into tomorrow's morning


class TimelineSkin:
    """Temperature, rain, and wind through today (and into tomorrow in landscape)."""

    name: ClassVar[str] = "timeline"

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
        if c.landscape:
            self._landscape(c, y)
        else:
            self._portrait(c, y)
        c.footer()
        return c.image

    def _portrait(self, c: Canvas, y: int) -> None:
        m = c.margin
        w = c.content_width
        y += c.px(30)
        icon = c.px(220)
        c.icon(c.snapshot.current.condition, (m, y, m + icon, y + icon), night=c.night)
        bottom = c.number(
            c.width - m + c.px(6),
            y - c.px(6),
            c.temperature(c.snapshot.current.temperature),
            220,
            w - icon - c.px(40),
        )
        c.text(
            (c.width - m, bottom + c.px(20)),
            c.condition_label(c.snapshot.current.condition),
            "medium",
            46,
            anchor="ra",
            max_width=w - icon - c.px(40),
        )
        c.text(
            (c.width - m, bottom + c.px(80)),
            self._range_line(c),
            "regular",
            36,
            fill=DARK_GRAY,
            anchor="ra",
        )
        y = max(y + icon, bottom + c.px(80) + c.px(50)) + c.px(40)
        y = self._tomorrow_row(c, m, y, w) + c.px(24)
        y = c.rule(m, y, w, PALE_GRAY, 3) + c.px(30)
        c.text((m, y), "Today, hour by hour", "bold", 36, anchor="la")
        y += c.px(60)
        hours = hours_from_midnight(c.snapshot.hourly, c.now, c.tz, _PORTRAIT_HOURS)
        self._chart(c, (m, y, c.width - m, c.height - m - c.px(50)), hours)

    def _landscape(self, c: Canvas, y: int) -> None:
        m = c.margin
        w = c.content_width
        y += c.px(30)
        icon = c.px(170)
        c.icon(c.snapshot.current.condition, (m, y, m + icon, y + icon), night=c.night)
        number_right = m + icon + c.px(250)
        c.number(
            number_right, y - c.px(6), c.temperature(c.snapshot.current.temperature), 170, c.px(240)
        )
        tx = number_right + c.px(40)
        c.text(
            (tx, y + c.px(10)),
            c.condition_label(c.snapshot.current.condition),
            "medium",
            46,
            anchor="la",
            max_width=w * 0.35,
        )
        c.text(
            (tx, y + c.px(72)),
            self._range_line(c),
            "regular",
            40,
            fill=DARK_GRAY,
            anchor="la",
            max_width=w * 0.35,
        )
        self._tomorrow_corner(c, y)
        y += icon + c.px(60)
        hours = hours_from_midnight(c.snapshot.hourly, c.now, c.tz, _LANDSCAPE_HOURS)
        self._chart(c, (m, y, c.width - m, c.height - m - c.px(50)), hours)

    # Blocks

    def _range_line(self, c: Canvas) -> str:
        line = c.range_text(c.snapshot.today)
        feels = c.feels_like_text()
        return f"{line}   ·   {feels[0].lower()}{feels[1:]}" if feels else line

    def _chart(
        self, c: Canvas, box: tuple[int, int, int, int], hours: list[HourlyForecast]
    ) -> None:
        left, top, right, bottom = box
        if len(hours) < 2:
            c.text(
                ((left + right) / 2, (top + bottom) / 2),
                "No hourly forecast",
                "regular",
                40,
                fill=DARK_GRAY,
                anchor="mm",
            )
            return
        draw_timeline(c.draw, box, hours, c.now, c.snapshot.sun, c.tz, c.time_format, c.scale)

    def _tomorrow_row(self, c: Canvas, x: int, y: int, width: int) -> int:
        """One line: "Tomorrow", its icon, range and condition, and the rain drop."""
        days = c.snapshot.daily
        if len(days) < 2:
            return y
        day = days[1]
        c.text((x, y), "Tomorrow", "bold", 36, anchor="la")
        c.icon(day.condition, (x + c.px(200), y - c.px(26), x + c.px(290), y + c.px(64)))
        c.text(
            (x + c.px(320), y + c.px(4)),
            f"{c.range_text(day)}   {c.condition_label(day.condition)}",
            "regular",
            38,
            fill=DARK_GRAY,
            anchor="la",
            max_width=width - c.px(320) - c.px(160),
        )
        self._rain(c, x + width, y + c.px(20), day.precipitation_probability)
        return y + c.px(70)

    def _tomorrow_corner(self, c: Canvas, y: int) -> None:
        """Tomorrow at the top right in landscape: name, range, rain, and its icon."""
        days = c.snapshot.daily
        if len(days) < 2:
            return
        day = days[1]
        right = c.width - c.margin
        icon = c.px(120)
        c.icon(day.condition, (right - icon, y + c.px(10), right, y + c.px(10) + icon))
        text_right = right - icon - c.px(20)
        c.text((text_right, y + c.px(16)), "Tomorrow", "bold", 34, anchor="ra")
        c.text(
            (text_right, y + c.px(62)),
            c.range_text(day),
            "regular",
            40,
            fill=DARK_GRAY,
            anchor="ra",
        )
        self._rain(c, text_right, y + c.px(140), day.precipitation_probability)

    def _rain(self, c: Canvas, right: float, cy: float, probability: float | None) -> None:
        """A drop filled to ``probability`` and the number, right-aligned at ``right``."""
        if probability is None:
            return
        note = f"{round(probability)}%"
        font = load_font("medium", c.px(34))
        note_w = c.draw.textlength(note, font=font)
        drop = c.px(30)
        drop_left = round(right - note_w - c.px(8) - drop)
        draw_drop(
            c.draw,
            (drop_left, round(cy - drop / 2), drop_left + drop, round(cy + drop / 2)),
            probability / 100,
            DARK_GRAY,
        )
        c.draw.text((right, cy), note, font=font, fill=DARK_GRAY, anchor="rm")
