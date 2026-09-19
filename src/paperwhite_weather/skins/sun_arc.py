"""The sun's day as one graphic: an arc over a horizon line instead of four clocks.

The arc is the upper half of an ellipse from sunrise to sunset over a horizon line; the
night half continues below the line as a faint dotted ellipse, and civil twilight is a
short thick gray band at each end, below the horizon. A filled disc marks the sun's
position by day; at night a crescent moon sits on the night half at the matching stage
of the night. Sunrise and sunset times are written under their ends of the horizon; the
civil dawn and dusk times go between them in small gray type when there is room.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, tzinfo

from PIL import ImageDraw

from paperwhite_weather.fonts import load_font
from paperwhite_weather.icons import Glyph
from paperwhite_weather.models import SunTimes
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, LIGHT_GRAY, WHITE, format_clock

#: Design measurements at scale 1 (a Paperwhite 3 canvas), in pixels.
_ARC_WIDTH = 6
_TWILIGHT_WIDTH = 14
_HORIZON_WIDTH = 3
_SUN_RADIUS = 20
_MOON_SIZE = 60
_LABEL_SIZE = 32
_SMALL_LABEL_SIZE = 24
_SEGMENTS = 64
#: Angle given to each civil-twilight band below the horizon, so it stays visible: civil
#: twilight is only a few percent of the day and at scale it would vanish.
_TWILIGHT_ANGLE = 0.85
#: The night half of the ellipse is flattened to this fraction of the day half.
_NIGHT_DEPTH = 0.35


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

    label_h = px(_LABEL_SIZE) + px(8)
    sun_r = min(px(_SUN_RADIUS), height // 8)
    night_depth = min(px(22), round(height * 0.12))
    horizon_y = bottom - label_h - night_depth - px(10)
    center_x = (left + right) / 2
    radius_x = width / 2 - sun_r - px(6)
    radius_y = max(sun_r * 2, min(horizon_y - top - sun_r - px(6), radius_x * 0.6))
    radius_night = min(night_depth, radius_y * _NIGHT_DEPTH)

    # Time to angle: sunrise at pi, sunset at 0, the twilight bands just below the
    # horizon at each end, the night in between below. Angles are conventional
    # (counterclockwise from three o'clock); the canvas y axis points down.
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
        sine = math.sin(theta)
        depth = radius_y if sine >= 0 else radius_night
        return (center_x + radius_x * math.cos(theta), horizon_y - depth * sine)

    def arc(start: float, end: float, fill: int, stroke: int, dotted: bool = False) -> None:
        points = [point(start + (end - start) * k / _SEGMENTS) for k in range(_SEGMENTS + 1)]
        if dotted:
            r = stroke / 2
            for x, y in points[::4]:
                draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)
        else:
            draw.line(points, fill=fill, width=stroke, joint="curve")

    arc(0, -math.pi, LIGHT_GRAY, px(5), dotted=True)  # the night, faint
    arc(math.pi, math.pi + phi, DARK_GRAY, px(_TWILIGHT_WIDTH))  # dawn
    arc(0, -phi, DARK_GRAY, px(_TWILIGHT_WIDTH))  # dusk
    arc(math.pi, 0, BLACK, px(_ARC_WIDTH))  # the day
    draw.line([(left, horizon_y), (right - 1, horizon_y)], fill=BLACK, width=px(_HORIZON_WIDTH))

    # Labels: sunrise under the left end, sunset under the right; both shrink together
    # until they fit side by side. Dawn and dusk go between them when there is room.
    def clock(moment: datetime) -> str:
        return format_clock(moment.astimezone(tz), time_format)

    sunrise_text, sunset_text = clock(sun.sunrise), clock(sun.sunset)
    label_size = px(_LABEL_SIZE)
    label_font = load_font("bold", label_size)
    while label_size > px(16):
        label_font = load_font("bold", label_size)
        needed = draw.textlength(sunrise_text, font=label_font) + draw.textlength(
            sunset_text, font=label_font
        )
        if needed + px(16) <= width:
            break
        label_size -= 1
    label_w = (
        draw.textlength(sunrise_text, font=label_font),
        draw.textlength(sunset_text, font=label_font),
    )

    # The sun: a filled disc on the arc by day; a crescent on the night half otherwise.
    if sun.civil_dawn <= now <= sun.civil_dusk:
        x, y = point(angle(now))
        ring = sun_r + px(5)
        draw.ellipse((x - ring, y - ring, x + ring, y + ring), fill=WHITE)
        draw.ellipse((x - sun_r, y - sun_r, x + sun_r, y + sun_r), fill=BLACK)
    else:
        next_dawn = sun.civil_dawn + timedelta(days=1)
        moment = now + timedelta(days=1) if now < sun.civil_dawn else now
        night = fraction(moment, sun.civil_dusk, next_dawn)
        x, _ = point(-phi - night * (math.pi - 2 * phi))
        # The crescent's bottom (0.725 of its size below its box top) stays above the
        # label row, and its box stays clear of the sunrise and sunset labels.
        moon = min(px(_MOON_SIZE), round((night_depth + px(6)) / 0.725))
        x = min(max(x, left + label_w[0] + moon / 2 + px(4)), right - label_w[1] - moon / 2 - px(4))
        glyph = Glyph(draw, x, horizon_y + moon * 0.45, moon)
        glyph.dot(0.0, 0.0, 0.8, WHITE)
        glyph.moon(0.0, 0.0, 0.55)

    label_y = bottom - label_h + px(4)
    draw.text((left, label_y), sunrise_text, font=label_font, fill=BLACK, anchor="la")
    draw.text((right, label_y), sunset_text, font=label_font, fill=BLACK, anchor="ra")
    small_font = load_font("regular", px(_SMALL_LABEL_SIZE))
    twilight = f"Dawn {clock(sun.civil_dawn)}  ·  Dusk {clock(sun.civil_dusk)}"
    room = width - label_w[0] - label_w[1] - px(48)
    if draw.textlength(twilight, font=small_font) <= room:
        draw.text(
            (center_x, label_y + px(6)), twilight, font=small_font, fill=DARK_GRAY, anchor="ma"
        )
