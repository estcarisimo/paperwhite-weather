"""Minimal skin: a large clock and temperature, today's range, a compact forecast."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from PIL import Image, ImageDraw

from paperwhite_weather.config import Settings
from paperwhite_weather.fonts import load_font
from paperwhite_weather.models import WeatherSnapshot
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

#: The layout is designed for the Paperwhite 3 portrait canvas and scaled down uniformly
#: when either dimension of the actual canvas is smaller (for example in landscape).
_DESIGN_WIDTH = 1072
_DESIGN_HEIGHT = 1448
_FORECAST_DAYS = 5


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
        scale = min(width / _DESIGN_WIDTH, height / _DESIGN_HEIGHT)
        margin = round(0.06 * width)
        content_width = width - 2 * margin
        tz = snapshot.location.tzinfo
        time_format = settings.display.time_format

        image = Image.new("L", size, WHITE)
        draw = ImageDraw.Draw(image)

        def px(design_px: float) -> int:
            return max(1, round(design_px * scale))

        # Masthead: date and clock.
        y = margin
        draw.text(
            (margin, y),
            f"{now:%A}, {now:%B} {now.day}",
            font=load_font("bold", px(46)),
            fill=BLACK,
            anchor="la",
        )
        y += px(70)
        clock = format_clock(now, time_format)
        draw.text(
            (margin, y),
            clock,
            font=fit_font(draw, clock, "bold", px(230), content_width),
            fill=BLACK,
            anchor="la",
        )
        y += px(290)
        draw.line([(margin, y), (width - margin, y)], fill=BLACK, width=px(4))
        y += px(40)

        # Lead: current temperature and conditions.
        temperature_font = load_font("bold", px(210))
        draw.text(
            (margin, y),
            format_temperature(snapshot.current.temperature),
            font=temperature_font,
            fill=BLACK,
            anchor="la",
        )
        temperature_width = draw.textlength(
            format_temperature(snapshot.current.temperature), font=temperature_font
        )
        detail_x = margin + temperature_width + px(30)
        draw.text(
            (detail_x, y + px(30)),
            CONDITION_LABELS[snapshot.current.condition],
            font=load_font("regular", px(56)),
            fill=BLACK,
            anchor="la",
        )
        today = snapshot.today
        draw.text(
            (detail_x, y + px(110)),
            f"H {format_temperature(today.temperature_high)}   "
            f"L {format_temperature(today.temperature_low)}",
            font=load_font("regular", px(48)),
            fill=DARK_GRAY,
            anchor="la",
        )
        if today.precipitation_probability is not None:
            draw.text(
                (detail_x, y + px(175)),
                f"Precipitation {round(today.precipitation_probability)}%",
                font=load_font("regular", px(40)),
                fill=DARK_GRAY,
                anchor="la",
            )
        y += px(280)

        # Sun events.
        sun = snapshot.sun
        sun_text = "   ".join(
            f"{label} {format_clock(moment.astimezone(tz), time_format)}"
            for label, moment in (
                ("Dawn", sun.civil_dawn),
                ("Sunrise", sun.sunrise),
                ("Sunset", sun.sunset),
                ("Dusk", sun.civil_dusk),
            )
        )
        draw.text(
            (margin, y),
            sun_text,
            font=fit_font(draw, sun_text, "regular", px(34), content_width),
            fill=BLACK,
            anchor="la",
        )
        y += px(70)
        draw.line([(margin, y), (width - margin, y)], fill=LIGHT_GRAY, width=px(2))
        y += px(40)

        # Forecast strip: the next days after today.
        upcoming = snapshot.daily[1 : _FORECAST_DAYS + 1]
        if upcoming:
            column_width = content_width / len(upcoming)
            for index, day in enumerate(upcoming):
                center_x = margin + column_width * (index + 0.5)
                draw.text(
                    (center_x, y),
                    f"{day.date:%a}",
                    font=load_font("bold", px(40)),
                    fill=BLACK,
                    anchor="ma",
                )
                draw.text(
                    (center_x, y + px(55)),
                    CONDITION_LABELS[day.condition],
                    font=load_font("regular", px(28)),
                    fill=DARK_GRAY,
                    anchor="ma",
                )
                draw.text(
                    (center_x, y + px(100)),
                    f"{format_temperature(day.temperature_high)} / "
                    f"{format_temperature(day.temperature_low)}",
                    font=load_font("regular", px(36)),
                    fill=BLACK,
                    anchor="ma",
                )

        # Footer: data freshness and units, so stale data is obvious.
        footer = (
            f"Updated {format_clock(snapshot.fetched_at.astimezone(tz), time_format)}"
            f"  ·  {snapshot.source}  ·  {snapshot.units.temperature_symbol}"
        )
        draw.text(
            (width - margin, height - margin),
            footer,
            font=load_font("regular", px(28)),
            fill=DARK_GRAY,
            anchor="rd",
        )
        return image
