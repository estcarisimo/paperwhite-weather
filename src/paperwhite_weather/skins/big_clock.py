"""Big-clock skin: the time dominates; weather is a strip at the bottom."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image

from paperwhite_weather.config import Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, LIGHT_GRAY
from paperwhite_weather.skins.common import Canvas


class BigClockSkin:
    """Readable from across the room: a clock first, a weather line second."""

    name: ClassVar[str] = "big-clock"

    def compose(
        self, snapshot: WeatherSnapshot, settings: Settings, now: datetime, size: tuple[int, int]
    ) -> Image.Image:
        """See :meth:`paperwhite_weather.skins.base.Skin.compose`."""
        c = Canvas(size, snapshot, settings, now)
        m = c.margin
        w = c.content_width

        # Clock, as large as the width allows, vertically in the upper part.
        clock = c.clock()
        clock_size = 520 if c.landscape else 360
        clock_y = c.height * (0.36 if c.landscape else 0.30)
        used = c.text((c.width / 2, clock_y), clock, "bold", clock_size, anchor="mm", max_width=w)
        c.text(
            (c.width / 2, clock_y + used * 0.78),
            c.date_line(),
            "regular",
            54,
            fill=DARK_GRAY,
            anchor="mm",
            max_width=w,
        )

        # Weather strip: icon, temperature, condition, range, sunrise/sunset.
        strip_top = c.height * (0.68 if c.landscape else 0.62)
        c.rule(m, strip_top, w, LIGHT_GRAY, 2)
        icon_size = c.px(190)
        icon_top = strip_top + c.px(40)
        c.icon(snapshot.current.condition, (m, icon_top, m + icon_size, icon_top + icon_size))
        x = m + icon_size + c.px(40)
        temp = c.temperature(snapshot.current.temperature)
        temp_size = c.text((x, icon_top - c.px(10)), temp, "bold", 170, anchor="la")
        x2 = x + c.text_width(temp, "bold", 170) + c.px(30)
        today = snapshot.today
        c.text(
            (x2, icon_top + c.px(10)),
            c.condition_label(snapshot.current.condition),
            "regular",
            50,
            anchor="la",
            max_width=c.width - m - x2,
        )
        c.text(
            (x2, icon_top + c.px(80)),
            c.high_low(today),
            "regular",
            44,
            fill=DARK_GRAY,
            anchor="la",
            max_width=c.width - m - x2,
        )
        sun = snapshot.sun
        c.text(
            (m, icon_top + max(icon_size, temp_size) + c.px(30)),
            f"Sunrise {c.clock(sun.sunrise)}     Sunset {c.clock(sun.sunset)}",
            "regular",
            40,
            fill=BLACK,
            anchor="la",
            max_width=w,
        )
        c.footer()
        return c.image
