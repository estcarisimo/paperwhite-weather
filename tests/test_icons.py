from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.icons import draw_icon
from paperwhite_weather.models import Condition


@pytest.mark.parametrize("condition", list(Condition))
@pytest.mark.parametrize("size", [12, 64, 300])
def test_every_condition_draws_inside_its_box(condition: Condition, size: int) -> None:
    pad = 20
    image = Image.new("L", (size + 2 * pad, size + 2 * pad), 255)
    draw_icon(ImageDraw.Draw(image), condition, (pad, pad, pad + size, pad + size))
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


def test_icons_differ_between_conditions() -> None:
    renders = {}
    for condition in Condition:
        image = Image.new("L", (100, 100), 255)
        draw_icon(ImageDraw.Draw(image), condition, (0, 0, 100, 100))
        renders[condition] = image.tobytes()
    assert len(set(renders.values())) == len(renders)
