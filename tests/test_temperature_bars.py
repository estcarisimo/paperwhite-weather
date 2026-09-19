"""Temperature bars: one shared axis, inside the box, a marker for now, graceful in narrow boxes."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.models import Condition
from paperwhite_weather.skins.temperature_bars import TemperatureRow, draw_temperature_bars

ROWS = [
    TemperatureRow("Today", 57, 75, Condition.PARTLY_CLOUDY, current=70, note="10%"),
    TemperatureRow("Sat", 54, 66, Condition.RAIN, note="80%"),
    TemperatureRow("Sun", 55, 70, Condition.THUNDERSTORM, note="65%"),
    TemperatureRow("Mon", 52, 64, Condition.CLOUDY, note="30%"),
    TemperatureRow("Tue", 48, 72, Condition.CLEAR, note="0%"),
]


def _render(rows: list[TemperatureRow], size: tuple[int, int], scale: float = 1.0) -> Image.Image:
    """Draw into a box with a white frame around it, so ink outside the box is detectable."""
    width, height = size
    image = Image.new("L", (width + 40, height + 40), 255)
    draw_temperature_bars(ImageDraw.Draw(image), (20, 20, 20 + width, 20 + height), rows, scale)
    return image


def _bar_span(
    image: Image.Image, row_index: int, rows: int, size: tuple[int, int]
) -> tuple[int, int]:
    """Leftmost and rightmost black pixel on the row's center line, excluding text: the
    bar is the longest run of black; return that run's ends."""
    cy = 20 + round((row_index + 0.5) * size[1] / rows)
    line = [image.getpixel((x, cy)) for x in range(image.width)]
    best, start = (0, 0), None
    for x, v in enumerate(line + [255]):
        if v == 0 and start is None:
            start = x
        elif v != 0 and start is not None:
            if x - start > best[1] - best[0]:
                best = (start, x)
            start = None
    return best


@pytest.mark.behaviour
@pytest.mark.parametrize(
    ("size", "scale"), [((960, 480), 1.0), ((560, 300), 0.6), ((640, 520), 0.7)]
)
def test_bars_stay_inside_their_box(size: tuple[int, int], scale: float) -> None:
    image = _render(ROWS, size, scale)
    width, height = image.size
    for box in (
        (0, 0, width, 20),
        (0, height - 20, width, height),
        (0, 0, 20, height),
        (width - 20, 0, width, height),
    ):
        assert image.crop(box).getextrema() == (255, 255), f"ink outside the box in {box}"
    assert image.getextrema()[0] == 0


@pytest.mark.behaviour
def test_bars_share_one_axis() -> None:
    """Equal temperatures land at equal x across rows; a wider range makes a longer bar."""
    size = (960, 480)
    image = _render(ROWS, size)
    # Rows 1-4 have no marker (the marker's white ring would split today's bar in two).
    spans = [_bar_span(image, k, len(ROWS), size) for k in range(len(ROWS))]
    lengths = [right - left for left, right in spans]
    # Tue (48-72) has the widest range and the longest bar; Sat and Mon both span 12
    # degrees and get bars of the same length; Sun (15 degrees) is longer than those.
    assert lengths[4] == max(lengths[1:])
    assert abs(lengths[1] - lengths[3]) <= 1
    assert lengths[2] > lengths[1]
    # Sun's low (55) sits one degree right of Sat's low (54), and Sat's high (66) is left
    # of Sun's high (70): the same axis for every row.
    assert 0 < spans[2][0] - spans[1][0] < 30
    assert spans[1][1] < spans[2][1]


@pytest.mark.behaviour
def test_today_carries_a_marker_for_the_current_temperature() -> None:
    size = (960, 480)
    with_marker = _render(ROWS, size)
    without = _render([replace(ROWS[0], current=None), *ROWS[1:]], size)
    row = (0, 20, 1000, 20 + size[1] // len(ROWS))
    assert with_marker.crop(row).histogram()[0] > without.crop(row).histogram()[0]


@pytest.mark.behaviour
@pytest.mark.parametrize("current", [57, 75, 40, 90, 66])
def test_marker_never_touches_the_values_at_the_bar_ends(current: float) -> None:
    """With current at, beyond, or inside the range, the low/high text is untouched."""
    size = (960, 480)
    # A reference row spanning every tested value keeps the axis identical in both renders.
    rest = [*ROWS[1:], TemperatureRow("Ref", 40, 90)]
    plain = _render([replace(ROWS[0], current=None), *rest], size)
    marked = _render([replace(ROWS[0], current=current), *rest], size)
    assert marked.tobytes() != plain.tobytes(), "no marker drawn"
    x_lo, x_hi = _bar_span(plain, 0, len(rest) + 1, size)
    row = size[1] // (len(rest) + 1)
    outside_left = (0, 20, x_lo - 1, 20 + row)
    outside_right = (x_hi + 1, 20, plain.width, 20 + row)
    assert marked.crop(outside_left).tobytes() == plain.crop(outside_left).tobytes()
    assert marked.crop(outside_right).tobytes() == plain.crop(outside_right).tobytes()


@pytest.mark.behaviour
@pytest.mark.parametrize(("low", "high"), [(60, 60), (60, 61), (60, 63)])
def test_marker_shrinks_on_a_flat_or_narrow_bar(low: float, high: float) -> None:
    """A bar narrower than the marker gets a smaller marker; the values stay untouched."""
    size = (600, 200)
    rest = [TemperatureRow("Sat", 40, 90)]
    plain = _render([TemperatureRow("Today", low, high), *rest], size)
    marked = _render([TemperatureRow("Today", low, high, current=low), *rest], size)
    assert marked.tobytes() != plain.tobytes(), "no marker drawn"
    x_lo, x_hi = _bar_span(plain, 0, 2, size)
    row = size[1] // 2
    outside_left = (0, 20, x_lo - 1, 20 + row)
    outside_right = (x_hi + 1, 20, plain.width, 20 + row)
    assert marked.crop(outside_left).tobytes() == plain.crop(outside_left).tobytes()
    assert marked.crop(outside_right).tobytes() == plain.crop(outside_right).tobytes()


@pytest.mark.behaviour
def test_narrow_boxes_drop_notes_then_icons_and_a_tiny_box_draws_nothing() -> None:
    """Whether notes or icons were drawn shows in whether removing them changes the frame."""
    no_notes = [replace(r, note=None) for r in ROWS]
    no_icons = [replace(r, condition=None) for r in ROWS]

    def drawn(size: tuple[int, int]) -> tuple[bool, bool]:
        full = _render(ROWS, size).tobytes()
        return full != _render(no_notes, size).tobytes(), full != _render(no_icons, size).tobytes()

    assert drawn((960, 480)) == (True, True)  # room for everything
    assert drawn((640, 480)) == (False, True)  # notes go first
    assert drawn((480, 480)) == (False, False)  # then the icons
    assert _render(ROWS, (480, 480)).getextrema()[0] == 0  # bars and values remain
    assert _render(ROWS, (120, 480)).getextrema() == (255, 255)  # nothing meaningful fits


@pytest.mark.behaviour
def test_flat_day_and_empty_rows() -> None:
    flat = [TemperatureRow("Today", 60, 60, None, current=60), TemperatureRow("Sat", 55, 65)]
    image = _render(flat, (600, 200))
    assert image.getextrema()[0] == 0
    # Every value equal: the axis is widened instead of dividing by zero.
    assert _render([TemperatureRow("Today", 60, 60, current=60)], (600, 100)).getextrema()[0] == 0
    assert _render([], (600, 200)).getextrema() == (255, 255)
