"""Monochrome weather icons drawn with Pillow primitives.

Every icon is drawn into a square box of the requested size on an existing ``"L"`` canvas,
so it scales with the layout and needs no bitmap assets or license. Shapes are simple on
purpose: filled forms and round-capped strokes survive 16 gray levels and 300 ppi e-ink
better than fine detail. ``CLEAR`` and ``PARTLY_CLOUDY`` have night variants (a moon in
place of the sun).
"""

from __future__ import annotations

import math

from PIL import ImageDraw

from paperwhite_weather.models import Condition

BLACK = 0
DARK_GRAY = 85
LIGHT_GRAY = 170
WHITE = 255


def draw_icon(
    draw: ImageDraw.ImageDraw,
    condition: Condition,
    box: tuple[int, int, int, int],
    night: bool = False,
) -> None:
    """Draw the icon for ``condition`` inside ``box`` (left, top, right, bottom).

    Parameters
    ----------
    draw
        Drawing context of an ``"L"`` image.
    condition
        Which icon.
    box
        Square-ish target area; the icon is centered and scaled to the shorter side.
    night
        Use the night variant where one exists (clear and partly cloudy show a moon).
    """
    left, top, right, bottom = box
    size = min(right - left, bottom - top)
    if size < 8:
        return
    cx = left + (right - left) / 2
    cy = top + (bottom - top) / 2
    glyph = Glyph(draw, cx, cy, size)
    drawer = _NIGHT_DRAWERS.get(condition) if night else None
    (drawer or _DRAWERS[condition])(glyph)


class Glyph:
    """Unit-square helper: coordinates in [-1, 1] mapped onto a box, round-capped strokes.

    Parameters
    ----------
    draw
        Drawing context of an ``"L"`` image.
    cx, cy
        Center of the box in canvas pixels.
    size
        Side of the box in canvas pixels; the unit square maps onto it.
    """

    def __init__(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float) -> None:
        self.draw = draw
        self.cx = cx
        self.cy = cy
        self.half = size / 2
        self.stroke = max(2, round(size * 0.075))

    def p(self, x: float, y: float) -> tuple[float, float]:
        """Canvas coordinates of the unit-square point ``(x, y)``."""
        return (self.cx + x * self.half, self.cy + y * self.half)

    def dot(self, x: float, y: float, r: float, fill: int = BLACK) -> None:
        """A filled disc of unit radius ``r``."""
        x0, y0 = self.p(x - r, y - r)
        x1, y1 = self.p(x + r, y + r)
        self.draw.ellipse([x0, y0, x1, y1], fill=fill)

    def stroke_line(
        self, x0: float, y0: float, x1: float, y1: float, fill: int = BLACK, width: int = 0
    ) -> None:
        """A line with round caps, ``width`` pixels wide (the default stroke when 0)."""
        width = width or self.stroke
        a, b = self.p(x0, y0), self.p(x1, y1)
        self.draw.line([a, b], fill=fill, width=width)
        r = width / 2
        for x, y in (a, b):
            self.draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def sun(
        self, x: float = 0.0, y: float = 0.0, r: float = 0.40, skip: tuple[int, ...] = ()
    ) -> None:
        """A disc with eight round rays; ``skip`` drops rays by index (0 = right, clockwise)."""
        self.dot(x, y, r)
        for k in range(8):
            if k in skip:
                continue
            a = k * math.pi / 4
            self.stroke_line(
                x + math.cos(a) * (r + 0.20),
                y + math.sin(a) * (r + 0.20),
                x + math.cos(a) * (r + 0.40),
                y + math.sin(a) * (r + 0.40),
            )

    def moon(self, x: float = 0.0, y: float = 0.0, r: float = 0.55) -> None:
        """A crescent: a disc with a second, white disc cut out of its upper right."""
        self.dot(x, y, r)
        self.dot(x + 0.42 * r, y - 0.30 * r, r * 0.82, WHITE)

    def cloud(self, x: float = 0.0, y: float = 0.12, scale: float = 1.0, fill: int = BLACK) -> None:
        """A cloud: a capsule base with two lobes, filled."""
        s = scale
        x0, y0 = self.p(x - 0.86 * s, y - 0.02 * s)
        x1, y1 = self.p(x + 0.86 * s, y + 0.44 * s)
        self.draw.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) / 2, fill=fill)
        self.dot(x - 0.34 * s, y - 0.10 * s, 0.34 * s, fill)
        self.dot(x + 0.16 * s, y - 0.26 * s, 0.46 * s, fill)

    def rain(self, count: int = 3, y: float = 0.72, dx: float = 0.34, length: float = 0.30) -> None:
        """Slanted round-capped strokes under a cloud."""
        start = -(count - 1) * dx / 2
        for k in range(count):
            x = start + k * dx
            self.stroke_line(x + 0.07, y - length / 2, x - 0.07, y + length / 2)

    def drizzle(self) -> None:
        """Five small dots in two staggered rows."""
        for x, y in ((-0.36, 0.62), (0.0, 0.70), (0.36, 0.62), (-0.18, 0.88), (0.18, 0.88)):
            self.dot(x, y, 0.065)

    def flakes(self, count: int = 3, y: float = 0.74, dx: float = 0.42) -> None:
        """Six-armed asterisks under a cloud."""
        start = -(count - 1) * dx / 2
        thin = max(1, round(self.stroke * 0.5))
        for k in range(count):
            x = start + k * dx
            for a in (0.0, math.pi / 3, 2 * math.pi / 3):
                self.stroke_line(
                    x + math.cos(a) * 0.15,
                    y + math.sin(a) * 0.15,
                    x - math.cos(a) * 0.15,
                    y - math.sin(a) * 0.15,
                    width=thin,
                )

    def bolt(self, x: float = 0.0, y: float = 0.62) -> None:
        """A lightning bolt polygon centered on ``(x, y)``."""
        points = [
            self.p(x + 0.14, y - 0.36),
            self.p(x - 0.18, y + 0.04),
            self.p(x + 0.03, y + 0.04),
            self.p(x - 0.14, y + 0.42),
            self.p(x + 0.22, y - 0.06),
            self.p(x, y - 0.06),
        ]
        self.draw.polygon(points, fill=BLACK)

    def fog_lines(self) -> None:
        """Three horizontal strokes of decreasing length, staggered."""
        for k, (y, length) in enumerate(((0.38, 0.72), (0.60, 0.60), (0.82, 0.44))):
            offset = 0.08 * (1 if k % 2 else -1)
            self.stroke_line(-length + offset, y, length + offset, y)


def _clear(g: Glyph) -> None:
    g.sun()


def _clear_night(g: Glyph) -> None:
    g.moon(0.0, 0.0, 0.62)


def _partly_cloudy(g: Glyph) -> None:
    # Rays toward the cloud are skipped rather than clipped by the halo.
    g.sun(-0.24, -0.22, 0.28, skip=(0, 1, 2))
    g.cloud(0.12, 0.22, 0.84, WHITE)  # halo so the cloud reads as in front of the sun
    g.cloud(0.12, 0.22, 0.72)


def _partly_cloudy_night(g: Glyph) -> None:
    g.moon(-0.24, -0.26, 0.40)
    g.cloud(0.12, 0.22, 0.84, WHITE)
    g.cloud(0.12, 0.22, 0.72)


def _cloudy(g: Glyph) -> None:
    g.cloud(0.0, 0.06, 0.96)


def _fog(g: Glyph) -> None:
    g.cloud(0.0, -0.30, 0.70, DARK_GRAY)
    g.fog_lines()


def _drizzle(g: Glyph) -> None:
    g.cloud(0.0, -0.24, 0.80)
    g.drizzle()


def _rain(g: Glyph) -> None:
    g.cloud(0.0, -0.24, 0.80)
    g.rain()


def _snow(g: Glyph) -> None:
    g.cloud(0.0, -0.28, 0.80)
    g.flakes()


def _thunderstorm(g: Glyph) -> None:
    g.cloud(0.0, -0.30, 0.78)
    g.bolt(0.0, 0.54)


def _unknown(g: Glyph) -> None:
    g.dot(0.0, 0.0, 0.7, DARK_GRAY)
    g.dot(0.0, 0.0, 0.7 - g.stroke / g.half, WHITE)
    g.stroke_line(-0.3, 0.0, 0.3, 0.0, DARK_GRAY)


_DRAWERS = {
    Condition.CLEAR: _clear,
    Condition.PARTLY_CLOUDY: _partly_cloudy,
    Condition.CLOUDY: _cloudy,
    Condition.FOG: _fog,
    Condition.DRIZZLE: _drizzle,
    Condition.RAIN: _rain,
    Condition.SNOW: _snow,
    Condition.THUNDERSTORM: _thunderstorm,
    Condition.UNKNOWN: _unknown,
}
_NIGHT_DRAWERS = {
    Condition.CLEAR: _clear_night,
    Condition.PARTLY_CLOUDY: _partly_cloudy_night,
}


def draw_drop(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    level: float | None = None,
    ink: int = BLACK,
) -> None:
    """Draw a water-drop outline in ``box``, filled from the bottom up to ``level``.

    Parameters
    ----------
    draw
        Drawing context of an ``"L"`` image.
    box
        Target area (left, top, right, bottom); the drop is centered on the shorter side.
    level
        Fraction in ``[0, 1]`` of the drop to fill (a probability or humidity); ``None`` or
        ``0`` leaves it hollow.
    ink
        Gray level of the outline and the fill.
    """
    left, top, right, bottom = box
    size = min(right - left, bottom - top)
    if size < 8:
        return
    cx = left + (right - left) / 2
    cy = top + (bottom - top) / 2
    stroke = max(2, round(size * 0.09))
    radius = size * 0.34
    center_y = cy + size * 0.14
    tip_y = cy - size * 0.5
    _drop_shape(draw, cx, center_y, radius, tip_y, ink)
    _drop_shape(draw, cx, center_y, radius - stroke, tip_y + stroke * 1.6, WHITE)
    if level is None or level <= 0:
        return
    level = min(level, 1.0)
    inner_r = radius - stroke
    inner_tip = tip_y + stroke * 1.6
    fill_y = (center_y + inner_r) - level * (center_y + inner_r - inner_tip)
    circle = (cx - inner_r, center_y - inner_r, cx + inner_r, center_y + inner_r)
    if fill_y >= center_y:
        # A circular segment: the arc below the level line, closed by its chord.
        start = math.asin(min(1.0, (fill_y - center_y) / inner_r))
        steps = 24
        points = [
            (cx + inner_r * math.cos(a), center_y + inner_r * math.sin(a))
            for a in (start + (math.pi - 2 * start) * k / steps for k in range(steps + 1))
        ]
        if len(points) >= 3:
            draw.polygon(points, fill=ink)
        return
    draw.ellipse(circle, fill=ink)
    # The part of the tip's triangle below the level line, as a trapezoid.
    p1, p2 = _drop_tangents(cx, center_y, inner_r, inner_tip)
    t = (fill_y - inner_tip) / max(p1[1] - inner_tip, 1e-6)
    left_x = cx + (p1[0] - cx) * t
    right_x = cx + (p2[0] - cx) * t
    draw.polygon([(left_x, fill_y), (right_x, fill_y), p2, p1], fill=ink)


def _drop_tangents(
    cx: float, cy: float, radius: float, tip_y: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Where the two lines from the tip touch the circle (left, right)."""
    distance = cy - tip_y
    angle = math.asin(min(1.0, radius / distance))
    reach = distance * math.cos(angle)
    return (
        (cx - math.sin(angle) * reach, tip_y + math.cos(angle) * reach),
        (cx + math.sin(angle) * reach, tip_y + math.cos(angle) * reach),
    )


def _drop_shape(
    draw: ImageDraw.ImageDraw, cx: float, cy: float, radius: float, tip_y: float, fill: int
) -> None:
    if radius <= 0 or tip_y >= cy - radius:
        return
    p1, p2 = _drop_tangents(cx, cy, radius, tip_y)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
    draw.polygon([(cx, tip_y), p1, p2], fill=fill)
