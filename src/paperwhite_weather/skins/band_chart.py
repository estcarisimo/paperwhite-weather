"""The week as one graphic: the daily high and low as two curves with the band between.

One column per day: the condition icon and the weekday on top, the high (black) and the
low (gray) as dots on smooth curves through all the days with a pale band between them,
each value written by its dot, and the precipitation probability as a filled drop with the
number at the bottom. Today's current temperature is a hollow ring on today's column.
"""

from __future__ import annotations

from PIL import ImageDraw

from paperwhite_weather.fonts import load_font
from paperwhite_weather.icons import draw_drop, draw_icon
from paperwhite_weather.models import DailyForecast
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, PALE_GRAY, WHITE, format_temperature

#: Design measurements at scale 1 (a Paperwhite 3 canvas), in pixels.
_ICON_SIZE = 96
_NAME_SIZE = 34
_VALUE_SIZE = 36
_NOTE_SIZE = 28
_DROP_SIZE = 30
_HIGH_WIDTH = 5
_LOW_WIDTH = 4
_DOT_RADIUS = 9
_RING_RADIUS = 14
_SMOOTH_STEPS = 12


def draw_band_chart(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    days: list[DailyForecast],
    current: float | None = None,
    scale: float = 1.0,
    long_names: bool = False,
) -> None:
    """Draw ``days`` as a high/low band chart inside ``box`` (left, top, right, bottom).

    Parameters
    ----------
    draw
        Target ``ImageDraw`` on a mode ``"L"`` image.
    box
        Pixel bounds; everything drawn stays inside. Columns share the width equally.
    days
        Forecast days in order, today first. Empty draws nothing.
    current
        The current temperature, marked as a hollow ring on the first column.
    scale
        Design-to-canvas factor, ``Canvas.scale`` in the shared skins.
    long_names
        Full weekday names instead of abbreviations (today is always "Today").
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    count = len(days)
    if not count or width < 10 or height < 10:
        return

    def px(design: float) -> int:
        return max(1, round(design * scale))

    icon = min(px(_ICON_SIZE), round(width / count * 0.8))
    value_font = load_font("medium", px(_VALUE_SIZE))
    name_font = load_font("bold", px(_NAME_SIZE))
    note_font = load_font("regular", px(_NOTE_SIZE))
    curve_top = top + icon + px(12) + px(_NAME_SIZE) + px(72)
    curve_bottom = bottom - px(40) - px(36)
    if curve_bottom - curve_top < px(40):
        return
    xs = [left + width * (k + 0.5) / count for k in range(count)]
    highs = [day.temperature_high for day in days]
    lows = [day.temperature_low for day in days]
    values = highs + lows + ([current] if current is not None else [])
    lo, hi = min(values), max(values)
    if hi - lo < 1:
        lo, hi = lo - 0.5, hi + 0.5

    def y_of(value: float) -> float:
        return curve_bottom - (value - lo) / (hi - lo) * (curve_bottom - curve_top)

    high_points = [(x, y_of(v)) for x, v in zip(xs, highs, strict=True)]
    low_points = [(x, y_of(v)) for x, v in zip(xs, lows, strict=True)]
    high_curve = _smooth(high_points)
    low_curve = _smooth(low_points)
    if count > 1:
        draw.polygon(high_curve + low_curve[::-1], fill=PALE_GRAY)
        draw.line(high_curve, fill=BLACK, width=px(_HIGH_WIDTH), joint="curve")
        draw.line(low_curve, fill=DARK_GRAY, width=px(_LOW_WIDTH), joint="curve")
    column = width / count
    for k, day in enumerate(days):
        x = xs[k]
        if k:
            divider = left + column * k
            draw.line([(divider, top), (divider, bottom - 1)], fill=PALE_GRAY, width=px(2))
        draw_icon(draw, day.condition, (round(x - icon / 2), top, round(x + icon / 2), top + icon))
        name = "Today" if k == 0 else (f"{day.date:%A}" if long_names else f"{day.date:%a}")
        draw.text((x, top + icon + px(12)), name, font=name_font, fill=BLACK, anchor="ma")
        for (px_, py_), value, fill, anchor, dy in (
            (high_points[k], highs[k], BLACK, "mb", -px(16)),
            (low_points[k], lows[k], DARK_GRAY, "mt", px(16)),
        ):
            r = px(_DOT_RADIUS)
            halo = r + px(4)
            draw.ellipse((px_ - halo, py_ - halo, px_ + halo, py_ + halo), fill=WHITE)
            draw.ellipse((px_ - r, py_ - r, px_ + r, py_ + r), fill=fill)
            draw.text(
                (px_, py_ + dy),
                format_temperature(value),
                font=value_font,
                fill=fill,
                anchor=anchor,
            )
        if k == 0 and current is not None:
            y = y_of(current)
            r = px(_RING_RADIUS)
            halo = r + px(5)
            draw.ellipse((x - halo, y - halo, x + halo, y + halo), fill=WHITE)
            draw.ellipse((x - r, y - r, x + r, y + r), outline=BLACK, width=px(5), fill=WHITE)
        probability = day.precipitation_probability
        if probability is not None:
            drop = px(_DROP_SIZE)
            note = f"{round(probability)}%"
            total = drop + px(6) + draw.textlength(note, font=note_font)
            drop_left = round(x - total / 2)
            cy = bottom - px(18)
            draw_drop(
                draw,
                (drop_left, round(cy - drop / 2), drop_left + drop, round(cy + drop / 2)),
                probability / 100,
                DARK_GRAY,
            )
            draw.text(
                (drop_left + drop + px(6), cy), note, font=note_font, fill=DARK_GRAY, anchor="lm"
            )


def _smooth(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """A Catmull-Rom spline through ``points`` (returned as is when fewer than three)."""
    if len(points) < 3:
        return points
    padded = [points[0], *points, points[-1]]
    out: list[tuple[float, float]] = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for step in range(_SMOOTH_STEPS):
            u = step / _SMOOTH_STEPS
            out.append(
                (
                    _catmull(p0[0], p1[0], p2[0], p3[0], u),
                    _catmull(p0[1], p1[1], p2[1], p3[1], u),
                )
            )
    out.append(points[-1])
    return out


def _catmull(a: float, b: float, c: float, d: float, u: float) -> float:
    return 0.5 * (
        2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u**3
    )
