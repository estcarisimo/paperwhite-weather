"""Monochrome weather icons drawn with Pillow primitives.

Every icon is drawn into a square box of the requested size on an existing ``"L"`` canvas,
so it scales with the layout and needs no bitmap assets or license. Shapes are simple on
purpose: bold strokes and filled forms survive 16 gray levels and 300 ppi e-ink better
than fine detail.
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
    draw: ImageDraw.ImageDraw, condition: Condition, box: tuple[int, int, int, int]
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
    """
    left, top, right, bottom = box
    size = min(right - left, bottom - top)
    if size < 8:
        return
    cx = left + (right - left) / 2
    cy = top + (bottom - top) / 2
    icon = _Icon(draw, cx, cy, size)
    _DRAWERS[condition](icon)


class _Icon:
    """Unit-square helper: coordinates in [-1, 1] mapped onto the box."""

    def __init__(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, size: float) -> None:
        self.draw = draw
        self.cx = cx
        self.cy = cy
        self.half = size / 2
        self.stroke = max(2, round(size * 0.07))

    def p(self, x: float, y: float) -> tuple[float, float]:
        return (self.cx + x * self.half, self.cy + y * self.half)

    def circle(self, x: float, y: float, r: float, fill: int | None, outline: int | None) -> None:
        x0, y0 = self.p(x - r, y - r)
        x1, y1 = self.p(x + r, y + r)
        self.draw.ellipse(
            [x0, y0, x1, y1], fill=fill, outline=outline, width=self.stroke if outline else 0
        )

    def line(self, x0: float, y0: float, x1: float, y1: float, fill: int = BLACK) -> None:
        self.draw.line([self.p(x0, y0), self.p(x1, y1)], fill=fill, width=self.stroke)

    def sun(self, x: float = 0.0, y: float = 0.0, r: float = 0.42, rays: bool = True) -> None:
        if rays:
            for k in range(8):
                a = k * math.pi / 4
                self.line(
                    x + math.cos(a) * (r + 0.16),
                    y + math.sin(a) * (r + 0.16),
                    x + math.cos(a) * (r + 0.42),
                    y + math.sin(a) * (r + 0.42),
                )
        self.circle(x, y, r, fill=BLACK, outline=None)

    def cloud(self, x: float = 0.0, y: float = 0.1, scale: float = 1.0, fill: int = BLACK) -> None:
        """A cloud made of three lobes on a flat base, filled."""
        s = scale
        # Base slab
        x0, y0 = self.p(x - 0.82 * s, y - 0.05 * s)
        x1, y1 = self.p(x + 0.82 * s, y + 0.42 * s)
        self.draw.rounded_rectangle([x0, y0, x1, y1], radius=0.22 * s * self.half, fill=fill)
        self.circle(x - 0.38 * s, y - 0.1 * s, 0.34 * s, fill=fill, outline=None)
        self.circle(x + 0.12 * s, y - 0.28 * s, 0.46 * s, fill=fill, outline=None)
        self.circle(x + 0.48 * s, y - 0.02 * s, 0.3 * s, fill=fill, outline=None)

    def drops(self, count: int, y: float = 0.72, dx: float = 0.34, length: float = 0.28) -> None:
        start = -(count - 1) * dx / 2
        for k in range(count):
            x = start + k * dx
            self.line(x + 0.08, y - length / 2, x - 0.08, y + length / 2)

    def flakes(self, count: int, y: float = 0.74, dx: float = 0.4) -> None:
        start = -(count - 1) * dx / 2
        thin = max(1, round(self.stroke * 0.5))
        for k in range(count):
            x = start + k * dx
            for a in (0.0, math.pi / 3, 2 * math.pi / 3):
                self.draw.line(
                    [
                        self.p(x + math.cos(a) * 0.15, y + math.sin(a) * 0.15),
                        self.p(x - math.cos(a) * 0.15, y - math.sin(a) * 0.15),
                    ],
                    fill=BLACK,
                    width=thin,
                )

    def bolt(self, x: float = 0.0, y: float = 0.66) -> None:
        pts = [
            self.p(x + 0.12, y - 0.34),
            self.p(x - 0.16, y + 0.04),
            self.p(x + 0.04, y + 0.04),
            self.p(x - 0.12, y + 0.4),
            self.p(x + 0.2, y - 0.06),
            self.p(x, y - 0.06),
        ]
        self.draw.polygon(pts, fill=BLACK)

    def fog_lines(self) -> None:
        for k, y in enumerate((0.36, 0.58, 0.8)):
            self.line(-0.7 + 0.1 * (k % 2), y, 0.7 - 0.1 * ((k + 1) % 2), y)


def _clear(i: _Icon) -> None:
    i.sun()


def _partly_cloudy(i: _Icon) -> None:
    i.sun(x=-0.26, y=-0.22, r=0.26)
    # White halo so the cloud reads as in front of the sun.
    i.cloud(x=0.12, y=0.2, scale=0.78, fill=WHITE)
    i.cloud(x=0.12, y=0.2, scale=0.7)


def _cloudy(i: _Icon) -> None:
    i.cloud(x=0.0, y=0.05, scale=0.95)


def _fog(i: _Icon) -> None:
    i.cloud(x=0.0, y=-0.3, scale=0.7, fill=DARK_GRAY)
    i.fog_lines()


def _drizzle(i: _Icon) -> None:
    i.cloud(x=0.0, y=-0.22, scale=0.8)
    i.drops(3, y=0.66, dx=0.36, length=0.16)


def _rain(i: _Icon) -> None:
    i.cloud(x=0.0, y=-0.22, scale=0.8)
    i.drops(3, y=0.7, dx=0.36, length=0.34)


def _snow(i: _Icon) -> None:
    i.cloud(x=0.0, y=-0.26, scale=0.8)
    i.flakes(3, y=0.7, dx=0.42)


def _thunderstorm(i: _Icon) -> None:
    i.cloud(x=0.0, y=-0.3, scale=0.78)
    i.bolt(x=0.0, y=0.52)


def _unknown(i: _Icon) -> None:
    i.circle(0.0, 0.0, 0.7, fill=None, outline=DARK_GRAY)
    i.line(-0.3, 0.0, 0.3, 0.0, fill=DARK_GRAY)


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
