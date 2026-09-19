"""The sun's day as one graphic: an arc over a horizon line instead of four clocks.

The arc is the upper part of an ellipse. Sunrise and sunset sit on the horizon line;
civil twilight continues the arc below the line in gray to dawn and dusk. A filled disc
marks the sun's position by day; at night a hollow disc sits under the horizon at the
matching stage of the night. Sunrise and sunset times are written under their marks,
dawn and dusk smaller and in gray at the ends.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, tzinfo

from PIL import ImageDraw

from paperwhite_weather.fonts import load_font
from paperwhite_weather.models import SunTimes
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, WHITE, format_clock

#: Design measurements at scale 1 (a Paperwhite 3 canvas), in pixels.
_ARC_WIDTH = 6
_HORIZON_WIDTH = 3
_TICK_HEIGHT = 22
_SUN_RADIUS = 20
_LABEL_SIZE = 34
_SMALL_LABEL_SIZE = 26
_SEGMENTS = 48
#: Angle given to each civil-twilight tail, so it stays visible: civil twilight is only a
#: few percent of the dawn-to-dusk span, and at scale it would vanish.
_TWILIGHT_ANGLE = 0.45


def draw_sun_arc(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    sun: SunTimes,
    now: datetime,
    tz: tzinfo,
    time_format: str,
    scale: float = 1.0,
) -> None:
    """Draw the sun arc inside ``box`` (left, top, right, bottom).

    Parameters
    ----------
    draw
        Target ``ImageDraw`` on a mode ``"L"`` image.
    box
        Pixel bounds; everything drawn stays inside. A width-to-height ratio near 2.5
        reads best; the arc adapts to any box.
    sun
        The day's civil dawn, sunrise, sunset, and civil dusk (timezone-aware).
    now
        The moment to mark the sun at (timezone-aware).
    tz, time_format
        For the time labels, as in :func:`paperwhite_weather.skins.base.format_clock`.
    scale
        Design-to-canvas factor, ``Canvas.scale`` in the shared skins.
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    if width < 10 or height < 10:
        return

    def px(design: float) -> int:
        return max(1, round(design * scale))

    label_font = load_font("bold", px(_LABEL_SIZE))
    small_font = load_font("regular", px(_SMALL_LABEL_SIZE))
    label_h = px(_LABEL_SIZE) + px(_SMALL_LABEL_SIZE) + px(18)
    sun_r = min(px(_SUN_RADIUS), height // 8)
    below = max(px(_TICK_HEIGHT), 2 * sun_r, round(0.22 * height))  # room for the tails
    horizon_y = bottom - label_h - below
    center_x = (left + right) / 2
    radius_x = width / 2 - sun_r - px(4)
    radius_y = max(sun_r * 2, horizon_y - top - sun_r - px(10))

    # Time to angle: dawn at pi + phi, sunrise at pi, sunset at 0, dusk at -phi, so the
    # twilight tails continue the ellipse below the horizon. Time is linear within each
    # of the three segments. Angles are conventional (counterclockwise from three
    # o'clock); the canvas y axis points down.
    phi = _TWILIGHT_ANGLE

    def fraction(moment: datetime, start: datetime, end: datetime) -> float:
        seconds = max((end - start).total_seconds(), 1.0)
        return min(max((moment - start).total_seconds() / seconds, 0.0), 1.0)

    def angle(moment: datetime) -> float:
        if moment < sun.sunrise:
            return math.pi + phi * (1 - fraction(moment, sun.civil_dawn, sun.sunrise))
        if moment <= sun.sunset:
            return math.pi * (1 - fraction(moment, sun.sunrise, sun.sunset))
        return -phi * fraction(moment, sun.sunset, sun.civil_dusk)

    def point(theta: float) -> tuple[float, float]:
        # The tails below the horizon are flattened so they stay clear of the labels.
        sine = math.sin(theta)
        depth = radius_y if sine >= 0 else radius_y * 0.5
        return (center_x + radius_x * math.cos(theta), horizon_y - depth * sine)

    def arc(start: float, end: float, fill: int) -> None:
        points = [point(start + (end - start) * k / _SEGMENTS) for k in range(_SEGMENTS + 1)]
        draw.line(points, fill=fill, width=px(_ARC_WIDTH), joint="curve")

    dawn, sunrise, sunset, dusk = (
        angle(sun.civil_dawn),
        angle(sun.sunrise),
        angle(sun.sunset),
        angle(sun.civil_dusk),
    )
    arc(dawn, sunrise, DARK_GRAY)
    arc(sunset, dusk, DARK_GRAY)
    arc(sunrise, sunset, BLACK)

    # Horizon with sunrise and sunset ticks.
    draw.line([(left, horizon_y), (right - 1, horizon_y)], fill=BLACK, width=px(_HORIZON_WIDTH))
    tick = px(_TICK_HEIGHT)
    for theta in (sunrise, sunset):
        x, _ = point(theta)
        draw.line([(x, horizon_y - tick // 2), (x, horizon_y + tick)], fill=BLACK, width=px(4))

    # The sun: filled on the arc by day, hollow under the horizon by night.
    if sun.civil_dawn <= now <= sun.civil_dusk:
        x, y = point(angle(now))
        ring = sun_r + px(5)
        draw.ellipse((x - ring, y - ring, x + ring, y + ring), fill=WHITE)
        draw.ellipse((x - sun_r, y - sun_r, x + sun_r, y + sun_r), fill=BLACK)
    else:
        next_dawn = sun.civil_dawn + timedelta(days=1)
        if now < sun.civil_dawn:
            now = now + timedelta(days=1)
        night = fraction(now, sun.civil_dusk, next_dawn)
        x = center_x + radius_x * math.cos(-phi - night * (math.pi - 2 * phi))
        y = horizon_y + sun_r * 0.5
        draw.ellipse(
            (x - sun_r, y - sun_r, x + sun_r, y + sun_r), outline=BLACK, width=px(4), fill=WHITE
        )

    # Labels: sunrise and sunset under their ticks, dawn and dusk small at the ends.
    label_y = horizon_y + below + px(4)
    sunrise_x, _ = point(sunrise)
    sunset_x, _ = point(sunset)

    def clock(moment: datetime) -> str:
        return format_clock(moment.astimezone(tz), time_format)

    sunrise_text, sunset_text = clock(sun.sunrise), clock(sun.sunset)
    room = sunset_x - sunrise_x - px(16)
    label_size = px(_LABEL_SIZE)
    while label_size > px(16):
        label_font = load_font("bold", label_size)
        needed = draw.textlength(sunrise_text, font=label_font) + draw.textlength(
            sunset_text, font=label_font
        )
        if needed <= room:
            break
        label_size -= 1
    draw.text((sunrise_x, label_y), sunrise_text, font=label_font, fill=BLACK, anchor="la")
    draw.text((sunset_x, label_y), sunset_text, font=label_font, fill=BLACK, anchor="ra")
    dawn_text, dusk_text = f"Dawn {clock(sun.civil_dawn)}", f"Dusk {clock(sun.civil_dusk)}"
    small_needed = draw.textlength(dawn_text, font=small_font) + draw.textlength(
        dusk_text, font=small_font
    )
    if small_needed + px(24) <= width:
        small_y = label_y + label_size + px(6)
        draw.text((left, small_y), dawn_text, font=small_font, fill=DARK_GRAY, anchor="la")
        draw.text((right, small_y), dusk_text, font=small_font, fill=DARK_GRAY, anchor="ra")
