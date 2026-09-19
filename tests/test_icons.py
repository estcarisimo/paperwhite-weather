from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.icons import draw_drop, draw_icon
from paperwhite_weather.models import Condition


@pytest.mark.parametrize("night", [False, True])
@pytest.mark.parametrize("condition", list(Condition))
@pytest.mark.parametrize("size", [12, 64, 300])
def test_every_condition_draws_inside_its_box(condition: Condition, size: int, night: bool) -> None:
    pad = 20
    image = Image.new("L", (size + 2 * pad, size + 2 * pad), 255)
    draw_icon(ImageDraw.Draw(image), condition, (pad, pad, pad + size, pad + size), night=night)
    # Something was drawn...
    assert image.getextrema()[0] < 255
    # ...and nothing outside the box (allow one pixel of stroke overhang).
    for box in (
        (0, 0, image.width, pad - 1),
        (0, image.height - pad + 1, image.width, image.height),
        (0, 0, pad - 1, image.height),
        (image.width - pad + 1, 0, image.width, image.height),
    ):
        assert image.crop(box).getextrema() == (255, 255), f"{condition} spills outside {box}"


def test_tiny_box_is_a_no_op() -> None:
    image = Image.new("L", (10, 10), 255)
    draw_icon(ImageDraw.Draw(image), Condition.RAIN, (0, 0, 6, 6))
    assert image.getextrema() == (255, 255)


def _render(condition: Condition, night: bool = False) -> bytes:
    image = Image.new("L", (100, 100), 255)
    draw_icon(ImageDraw.Draw(image), condition, (0, 0, 100, 100), night=night)
    return image.tobytes()


def test_icons_differ_between_conditions() -> None:
    renders = {condition: _render(condition) for condition in Condition}
    assert len(set(renders.values())) == len(renders)


def test_night_changes_only_the_sun_icons() -> None:
    """Clear and partly cloudy get a moon at night; every other icon is the same day or night."""
    for condition in Condition:
        differs = _render(condition) != _render(condition, night=True)
        assert differs == (condition in (Condition.CLEAR, Condition.PARTLY_CLOUDY)), condition


@pytest.mark.parametrize("size", [12, 34, 120])
def test_drop_stays_inside_its_box_and_fills_with_the_level(size: int) -> None:
    pad = 20

    def ink(level: float | None) -> int:
        image = Image.new("L", (size + 2 * pad, size + 2 * pad), 255)
        draw_drop(ImageDraw.Draw(image), (pad, pad, pad + size, pad + size), level)
        for box in (
            (0, 0, image.width, pad - 1),
            (0, image.height - pad + 1, image.width, image.height),
            (0, 0, pad - 1, image.height),
            (image.width - pad + 1, 0, image.width, image.height),
        ):
            assert image.crop(box).getextrema() == (255, 255), f"drop spills outside {box}"
        return image.histogram()[0]

    hollow, low, half, full = ink(None), ink(0.1), ink(0.5), ink(1.0)
    assert 0 < hollow == ink(0.0) < low < half < full


def test_tiny_drop_is_a_no_op() -> None:
    image = Image.new("L", (10, 10), 255)
    draw_drop(ImageDraw.Draw(image), (0, 0, 6, 6), 0.5)
    assert image.getextrema() == (255, 255)
