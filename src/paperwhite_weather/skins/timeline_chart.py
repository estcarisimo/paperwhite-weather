"""The day hour by hour as one graphic: temperature curve, rain bars, wind, night shading.

Hours run left to right. The temperature is a smooth curve with its value written every
three hours and a marker where the time is now; the hours between sunset and sunrise are
shaded; the precipitation probability is a bar per hour under the curve; the wind is a
row of strokes whose length follows the speed; the condition icon (night variants after
sunset) sits above every third hour; a midnight inside the span gets a divider and the
new weekday.
"""

from __future__ import annotations

from datetime import datetime, tzinfo

from PIL import ImageDraw

from paperwhite_weather.fonts import load_font
from paperwhite_weather.icons import draw_drop, draw_icon, draw_wind
from paperwhite_weather.models import HourlyForecast, SunTimes
from paperwhite_weather.skins.band_chart import _smooth
from paperwhite_weather.skins.base import (
    BLACK,
    DARK_GRAY,
    LIGHT_GRAY,
    WHITE,
    format_temperature,
)

#: Design measurements at scale 1 (a Paperwhite 3 canvas), in pixels.
_ICON_SIZE = 56
_LABEL_SIZE = 28
_VALUE_SIZE = 30
_RAIN_HEIGHT = 90
_WIND_HEIGHT = 70
_CURVE_WIDTH = 6
_NIGHT_SHADE = 232
_LABEL_EVERY = 3


def draw_timeline(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    hours: list[HourlyForecast],
    now: datetime,
    sun: SunTimes,
    tz: tzinfo,
    time_format: str,
    scale: float = 1.0,
    wind: bool = True,
) -> None:
    """Draw ``hours`` as the timeline inside ``box`` (left, top, right, bottom).

    Parameters
    ----------
    draw
        Target ``ImageDraw`` on a mode ``"L"`` image.
    box
        Pixel bounds; everything drawn stays inside. Leave a strip of about 40 design
        pixels free on the left of the box for the rain and wind glyphs.
    hours
        Consecutive hours in ascending order, at least two; today's local midnight
        first reads best. Fewer than two draws nothing.
    now
        The moment to mark (timezone-aware).
    sun
        Today's sun times; their sunrise and sunset times of day shade every day in the
        span (the day-to-day drift is minutes, below the width of an hour).
    tz, time_format
        For the hour labels, as in :func:`paperwhite_weather.skins.base.format_clock`.
    scale
        Design-to-canvas factor, ``Canvas.scale`` in the shared skins.
    wind
        Draw the wind row (dropped in short boxes automatically).
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    count = len(hours)
    if count < 2 or width < 40 or height < 40:
        return

    def px(design: float) -> int:
        return max(1, round(design * scale))

    label_h = px(_LABEL_SIZE) + px(28)
    rain_h = px(_RAIN_HEIGHT)
    wind_h = px(_WIND_HEIGHT) if wind and height > px(420) else 0
    icon = px(_ICON_SIZE)
    curve_top = top + icon + px(54)
    curve_bottom = bottom - label_h - rain_h - wind_h - px(30)
    if curve_bottom - curve_top < px(60):
        return
    label_font = load_font("medium", px(_LABEL_SIZE))
    value_font = load_font("bold", px(_VALUE_SIZE))
    day_font = load_font("bold", px(26))
    glyph_left = left + px(4)
    plot_left = left + px(40)
    plot_right = right - px(30)  # room for the last hour label and the curve's cap
    step = (plot_right - plot_left) / (count - 1)

    def x_of(index: float) -> float:
        return plot_left + step * index

    def dark(moment: datetime) -> bool:
        # Today's sunrise and sunset times of day stand in for every day in the span;
        # the drift from one day to the next is a few minutes, below an hour's width.
        local = moment.astimezone(tz)
        sunrise = sun.sunrise.astimezone(tz).replace(
            year=local.year, month=local.month, day=local.day
        )
        sunset = sun.sunset.astimezone(tz).replace(
            year=local.year, month=local.month, day=local.day
        )
        return not (sunrise <= local <= sunset)

    # Night shading behind everything but the icons and the hour labels.
    index = 0
    while index < count:
        if dark(hours[index].time):
            end = index
            while end < count and dark(hours[end].time):
                end += 1
            draw.rectangle(
                (x_of(index), curve_top - px(40), x_of(min(end, count - 1)), bottom - label_h),
                fill=_NIGHT_SHADE,
            )
            index = end
        else:
            index += 1

    temperatures = [hour.temperature for hour in hours]
    lo, hi = min(temperatures), max(temperatures)
    if hi - lo < 1:
        lo, hi = lo - 0.5, hi + 0.5

    def y_of(value: float) -> float:
        return curve_bottom - (value - lo) / (hi - lo) * (curve_bottom - curve_top)

    points = [(x_of(k), y_of(t)) for k, t in enumerate(temperatures)]
    draw.line(_smooth(points), fill=BLACK, width=px(_CURVE_WIDTH), joint="curve")

    # Rain bars under the curve, darker from 50 % up; a drop glyph on the left.
    rain_top = curve_bottom + px(24)
    baseline = rain_top + rain_h * 0.85
    for k, hour in enumerate(hours):
        probability = hour.precipitation_probability
        if probability is None or probability < 3:
            continue
        bar = rain_h * 0.85 * probability / 100
        x0, x1 = x_of(k) - step * 0.32, x_of(k) + step * 0.32
        fill = DARK_GRAY if probability >= 50 else LIGHT_GRAY
        draw.rectangle((x0, baseline - bar, x1, baseline), fill=fill)
    draw.line([(plot_left, baseline), (plot_right, baseline)], fill=LIGHT_GRAY, width=px(2))
    drop = px(26)
    draw_drop(
        draw,
        (
            glyph_left,
            round(baseline - rain_h * 0.4 - drop / 2),
            glyph_left + drop,
            round(baseline - rain_h * 0.4 + drop / 2),
        ),
        0.6,
        DARK_GRAY,
    )

    # Wind: a stroke every other hour whose length follows the speed.
    if wind_h:
        wind_y = baseline + px(10) + wind_h / 2
        speeds = [hour.wind_speed for hour in hours if hour.wind_speed is not None]
        peak = max(speeds) if speeds else 0.0
        for k, hour in enumerate(hours):
            if k % 2 or hour.wind_speed is None or peak <= 0:
                continue
            length = px(10) + px(26) * hour.wind_speed / peak
            x = x_of(k)
            draw.line(
                [(x - length / 2, wind_y), (x + length / 2, wind_y)], fill=DARK_GRAY, width=px(5)
            )
            r = px(3)
            draw.ellipse(
                (x + length / 2 - r, wind_y - r, x + length / 2 + r, wind_y + r), fill=DARK_GRAY
            )
        glyph = px(30)
        draw_wind(
            draw,
            (glyph_left, round(wind_y - glyph / 2), glyph_left + glyph, round(wind_y + glyph / 2)),
            DARK_GRAY,
        )

    # Midnight dividers first, so the labels and values drawn next sit on top of them.
    for k, hour in enumerate(hours):
        local = hour.time.astimezone(tz)
        if local.hour == 0 and k and k < count - 3:
            x = x_of(k)
            draw.line([(x, top), (x, bottom - label_h)], fill=DARK_GRAY, width=px(2))
            draw.text(
                (x + px(8), top + px(60)), f"{local:%A}", font=day_font, fill=DARK_GRAY, anchor="la"
            )

    # Hour labels, ticks, values, and icons.
    for k, hour in enumerate(hours):
        local = hour.time.astimezone(tz)
        x = x_of(k)
        if local.hour % _LABEL_EVERY == 0:
            draw.text(
                (x, bottom - label_h + px(10)),
                _hour_label(local, time_format),
                font=label_font,
                fill=BLACK if local.hour == 0 else DARK_GRAY,
                anchor="ma",
            )
            draw.line(
                [(x, bottom - label_h), (x, bottom - label_h + px(8))], fill=DARK_GRAY, width=px(2)
            )
            # The value goes on the outside of the curve (above a crest or a level run,
            # below a trough) with a white halo, so a steep segment never crosses it.
            neighbors = [temperatures[j] for j in (k - 1, k + 1) if 0 <= j < count]
            above = sum(neighbors) / len(neighbors) <= hour.temperature
            draw.text(
                (x, y_of(hour.temperature) + (-px(16) if above else px(16))),
                format_temperature(hour.temperature),
                font=value_font,
                fill=BLACK,
                anchor="mb" if above else "mt",
                stroke_width=px(4),
                stroke_fill=WHITE,
            )
        if local.hour % _LABEL_EVERY == 1 and k + 1 < count:
            cx = x_of(k + 1)
            draw_icon(
                draw,
                hour.condition,
                (round(cx - icon / 2), top, round(cx + icon / 2), top + icon),
                night=dark(hour.time),
            )

    # The marker for now: a vertical line and a disc on the curve.
    position = (now - hours[0].time).total_seconds() / 3600
    if 0 <= position <= count - 1:
        index = min(int(position), count - 2)
        fraction = position - index
        value = temperatures[index] + (temperatures[index + 1] - temperatures[index]) * fraction
        x, y = x_of(position), y_of(value)
        draw.line([(x, top + icon + px(8)), (x, bottom - label_h)], fill=BLACK, width=px(3))
        r = px(11)
        halo = r + px(5)
        draw.ellipse((x - halo, y - halo, x + halo, y + halo), fill=WHITE)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=BLACK)


def _hour_label(moment: datetime, time_format: str) -> str:
    """``"3p"`` / ``"12a"`` in 12-hour format, ``"15"`` in 24-hour format."""
    if time_format == "12h":
        hour = moment.hour % 12 or 12
        return f"{hour}{'a' if moment.hour < 12 else 'p'}"
    return f"{moment:%H}"


def hours_from_midnight(
    hours: list[HourlyForecast], now: datetime, tz: tzinfo, count: int
) -> list[HourlyForecast]:
    """Up to ``count`` hours starting at the local midnight of ``now``'s day."""
    midnight = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return [hour for hour in hours if hour.time >= midnight][:count]
