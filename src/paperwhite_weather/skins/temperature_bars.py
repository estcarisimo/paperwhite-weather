"""Temperature ranges as bars on one shared scale, so the days compare at a glance.

One row per day: a label, an optional condition icon, a bar from the day's low to its
high, the two values at the bar's ends, and an optional note (precipitation probability)
in gray at the right. All bars share one axis. A row with a ``current`` temperature
(today) gets a disc on its bar where the temperature is now.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import ImageDraw

from paperwhite_weather.fonts import load_font
from paperwhite_weather.icons import draw_icon
from paperwhite_weather.models import Condition, DailyForecast, WeatherSnapshot
from paperwhite_weather.skins.base import BLACK, DARK_GRAY, WHITE, format_temperature

#: Design measurements at scale 1 (a Paperwhite 3 canvas), in pixels.
_LABEL_SIZE = 40
_VALUE_SIZE = 38
_NOTE_SIZE = 30
_BAR_HEIGHT = 26
_ICON_SIZE = 90
_GAP = 14
#: Shortest axis worth drawing; below it the notes, then the icons, are dropped.
_MIN_AXIS = 200
#: Rows taller than the design row grow their type, bars, and icons up to this factor.
_MAX_GROWTH = 1.4
_DESIGN_ROW = 110


@dataclass(frozen=True)
class TemperatureRow:
    """One bar: ``label`` (day), ``low``/``high``, optional icon, marker, and note."""

    label: str
    low: float
    high: float
    condition: Condition | None = None
    current: float | None = None
    note: str | None = None


def rows_for_days(
    snapshot: WeatherSnapshot, days: list[DailyForecast], long_names: bool = False
) -> list[TemperatureRow]:
    """Bar rows for ``days``: today is labeled "Today" and carries the current temperature.

    Parameters
    ----------
    snapshot
        Source of today's date and the current temperature.
    days
        Forecast days to show, in order.
    long_names
        Full weekday names (``"Saturday"``) instead of abbreviations (``"Sat"``).
    """
    today = snapshot.today.date
    rows = []
    for day in days:
        is_today = day.date == today
        label = "Today" if is_today else f"{day.date:%A}" if long_names else f"{day.date:%a}"
        note = None
        if day.precipitation_probability is not None:
            note = f"{round(day.precipitation_probability)}%"
        rows.append(
            TemperatureRow(
                label=label,
                low=day.temperature_low,
                high=day.temperature_high,
                condition=day.condition,
                current=snapshot.current.temperature if is_today else None,
                note=note,
            )
        )
    return rows


def draw_temperature_bars(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    rows: list[TemperatureRow],
    scale: float = 1.0,
) -> None:
    """Draw ``rows`` as aligned bars inside ``box`` (left, top, right, bottom).

    Parameters
    ----------
    draw
        Target ``ImageDraw`` on a mode ``"L"`` image.
    box
        Pixel bounds; everything drawn stays inside. Rows share the height equally.
    rows
        Days to draw, top to bottom. Empty draws nothing.
    scale
        Design-to-canvas factor, ``Canvas.scale`` in the shared skins.
    """
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    if not rows or width < 10 or height < 10:
        return

    def px(design: float) -> int:
        return max(1, round(design * scale))

    row_h = height / len(rows)
    gap = px(_GAP)
    has_icons = any(r.condition for r in rows)
    has_notes = any(r.note for r in rows)

    # Tall rows grow the type, bars, and icons. A narrow box gives up, in order, the
    # growth, the notes, and the icons, before the bars get too short to read.
    growth = min(max(row_h / px(_DESIGN_ROW), 1.0), _MAX_GROWTH)
    attempts = [
        (g, notes, icons)
        for notes, icons in ((True, True), (False, True), (False, False))
        for g in (growth, 1.0)
    ]
    for growth, with_notes, with_icons in dict.fromkeys(attempts):
        label_font = load_font("bold", min(px(_LABEL_SIZE * growth), round(row_h * 0.55)))
        value_font = load_font("regular", min(px(_VALUE_SIZE * growth), round(row_h * 0.5)))
        note_font = load_font("regular", min(px(_NOTE_SIZE * growth), round(row_h * 0.4)))
        bar_h = min(px(_BAR_HEIGHT * growth), round(row_h * 0.3))
        icon = min(px(_ICON_SIZE * growth), round(row_h * 0.85)) if has_icons and with_icons else 0
        label_w = max(draw.textlength(r.label, font=label_font) for r in rows)
        value_w = max(
            draw.textlength(format_temperature(v), font=value_font)
            for r in rows
            for v in (r.low, r.high)
        )
        note_w = 0.0
        if has_notes and with_notes:
            note_w = max(draw.textlength(r.note, font=note_font) for r in rows if r.note)
        bar_left = left + label_w + gap + (icon + gap if icon else 0) + value_w + gap
        bar_right = right - value_w - gap - (note_w + gap if note_w else 0)
        if bar_right - bar_left >= px(_MIN_AXIS):
            break
    if bar_right - bar_left < 4 * bar_h:
        return  # not enough room for bars that mean anything

    # Shared axis over every low, high, and current value.
    values = [v for r in rows for v in (r.low, r.high, r.current) if v is not None]
    axis_lo, axis_hi = min(values), max(values)
    if axis_hi - axis_lo < 1:
        axis_lo, axis_hi = axis_lo - 0.5, axis_hi + 0.5

    def x_of(value: float) -> float:
        return bar_left + (value - axis_lo) / (axis_hi - axis_lo) * (bar_right - bar_left)

    for k, row in enumerate(rows):
        cy = top + row_h * (k + 0.5)
        x: float = left
        draw.text((x, cy), row.label, font=label_font, fill=BLACK, anchor="lm")
        x += label_w + gap
        if icon:
            if row.condition is not None:
                draw_icon(
                    draw,
                    row.condition,
                    (round(x), round(cy - icon / 2), round(x + icon), round(cy + icon / 2)),
                )
            x += icon + gap
        x_lo, x_hi = x_of(row.low), x_of(row.high)
        if x_hi - x_lo < bar_h:  # a flat day still shows as a dot-sized bar
            mid = (x_lo + x_hi) / 2
            x_lo, x_hi = mid - bar_h / 2, mid + bar_h / 2
        draw.text(
            (x_lo - gap, cy), format_temperature(row.low), font=value_font, fill=BLACK, anchor="rm"
        )
        draw.rounded_rectangle(
            (x_lo, cy - bar_h / 2, x_hi, cy + bar_h / 2), radius=bar_h / 2, fill=BLACK
        )
        draw.text(
            (x_hi + gap, cy), format_temperature(row.high), font=value_font, fill=BLACK, anchor="lm"
        )
        if row.current is not None:
            # The marker, ring included, stays within the bar's extent so it never
            # touches the values at the ends (current at, or beyond, the low or high).
            # A bar narrower than the full-size marker (a flat or near-flat day) gets a
            # smaller one: ``ring`` never exceeds the bar's half width, so the clamp's
            # interval [x_lo + ring, x_hi - ring] is never empty.
            half = (x_hi - x_lo) / 2
            ring = min(bar_h * 0.9 + px(4), half)
            r = max(ring - px(4), ring * 0.6)
            cx = min(max(x_of(row.current), x_lo + ring), x_hi - ring)
            draw.ellipse((cx - ring, cy - ring, cx + ring, cy + ring), fill=WHITE)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=BLACK)
        if row.note and note_w:
            draw.text((right, cy), row.note, font=note_font, fill=DARK_GRAY, anchor="rm")
