"""The band chart stays inside its box, orders values on one axis, and degrades."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.models import Condition, DailyForecast
from paperwhite_weather.skins.band_chart import _ICON_SIZE, _NAME_SIZE, draw_band_chart

_DAYS = (
    (Condition.PARTLY_CLOUDY, 57, 75, 10),
    (Condition.RAIN, 54, 66, 80),
    (Condition.THUNDERSTORM, 55, 70, 65),
    (Condition.CLOUDY, 52, 64, 30),
    (Condition.CLEAR, 48, 72, 0),
)


def _days(count: int = 5, probability: bool = True) -> list[DailyForecast]:
    return [
        DailyForecast(
            date=date(2026, 9, 18) + timedelta(days=k),
            condition=condition,
            temperature_low=low,
            temperature_high=high,
            precipitation_probability=chance if probability else None,
        )
        for k, (condition, low, high, chance) in enumerate(_DAYS[:count])
    ]


def _render(
    days: list[DailyForecast], size: tuple[int, int], scale: float = 1.0, current: float | None = 70
) -> Image.Image:
    """Draw into a box with a white frame around it, so ink outside the box is detectable."""
    width, height = size
    image = Image.new("L", (width + 40, height + 40), 255)
    draw_band_chart(ImageDraw.Draw(image), (20, 20, 20 + width, 20 + height), days, current, scale)
    return image


@pytest.mark.behaviour
@pytest.mark.parametrize(
    ("size", "scale"), [((960, 520), 1.0), ((700, 800), 1.0), ((560, 320), 0.6)]
)
def test_chart_stays_inside_its_box(size: tuple[int, int], scale: float) -> None:
    image = _render(_days(), size, scale)
    width, height = image.size
    for box in (
        (0, 0, width, 20),
        (0, height - 20, width, height),
        (0, 0, 20, height),
        (width - 20, 0, width, height),
    ):
        assert image.crop(box).getextrema() == (255, 255), f"ink outside the box in {box}"
    assert image.getextrema()[0] == 0, "nothing drawn"


@pytest.mark.behaviour
def test_higher_temperatures_sit_higher_on_one_axis() -> None:
    """The high dot of the warmest day is the topmost black dot; the coldest low the lowest."""
    days = _days()
    image = _render(days, (960, 520), current=None)
    column = 960 / len(days)

    def dot_rows(k: int) -> list[int]:
        x = 20 + round(column * (k + 0.5))
        return [y for y in range(20, 540) if image.getpixel((x, y)) < 128]  # dots, black or gray

    # Tue (72/48) spans the widest: its high sits above Sat's high (66) and its low
    # below Sat's low (54) on the same axis.
    tue, sat = dot_rows(4), dot_rows(1)
    assert tue and sat
    band = (20 + _ICON_SIZE + 12 + _NAME_SIZE + 72, 540 - 40 - 36)  # the curve area
    tue_in = [y for y in tue if band[0] <= y <= band[1]]
    sat_in = [y for y in sat if band[0] <= y <= band[1]]
    assert min(tue_in) < min(sat_in) and max(tue_in) > max(sat_in)


@pytest.mark.behaviour
def test_one_day_no_probability_and_a_tiny_box_degrade_gracefully() -> None:
    assert _render(_days(1), (400, 400)).getextrema()[0] == 0
    assert _render(_days(2, probability=False), (600, 400)).getextrema()[0] == 0
    flat = [
        d.model_copy(update={"temperature_low": 60.0, "temperature_high": 60.0}) for d in _days(3)
    ]
    assert _render(flat, (600, 400), current=60).getextrema()[0] == 0
    assert _render([], (600, 400)).getextrema() == (255, 255)
    assert _render(_days(), (300, 60)).getextrema() == (255, 255)  # no room for curves


@pytest.mark.behaviour
@pytest.mark.parametrize("current", [75, 74, 72, 70, 66, 60, 58, 57])
def test_ring_never_touches_the_dots(current: float) -> None:
    """Today's ring appears only with clear room; the high and low dots are never overpainted.

    Currents stay within the week's range so the axis, and the dots, are the same in both
    renders; the checked box is the dot plus its white halo.
    """
    days = _days()
    plain = _render(days, (960, 520), current=None)
    marked = _render(days, (960, 520), current=current)
    column = 960 / len(days)
    x = 20 + column * 0.5
    # The dots of today's column: the topmost and bottommost dark pixels on its center line.
    rows = [
        y
        for y in range(20 + _ICON_SIZE + 12 + _NAME_SIZE + 72, 540 - 76)
        if plain.getpixel((round(x), y)) < 128
    ]
    high_y, low_y = min(rows), max(rows)
    for center in (high_y + 9, low_y - 9):
        box = (round(x) - 13, center - 13, round(x) + 13, center + 13)
        assert marked.crop(box).tobytes() == plain.crop(box).tobytes(), "a dot was touched"


def test_ring_is_drawn_when_there_is_room_and_skipped_on_a_flat_day() -> None:
    days = _days()
    assert (
        _render(days, (960, 520), current=66).tobytes()
        != _render(days, (960, 520), current=None).tobytes()
    )
    flat = [d.model_copy(update={"temperature_low": 60.0, "temperature_high": 60.0}) for d in days]
    assert (
        _render(flat, (960, 520), current=60).tobytes()
        == _render(flat, (960, 520), current=None).tobytes()
    )
