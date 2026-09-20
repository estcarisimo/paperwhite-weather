"""The sun arc stays inside its box, marks the sun by day and by night, and degrades."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.models import SunTimes
from paperwhite_weather.skins import sun_arc
from paperwhite_weather.skins.sun_arc import draw_sun_arc

TZ = ZoneInfo("America/Chicago")


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 19, hour, minute, tzinfo=TZ)


@pytest.fixture
def sun() -> SunTimes:
    return SunTimes(
        civil_dawn=_at(6, 53), sunrise=_at(7, 17), sunset=_at(19, 30), civil_dusk=_at(19, 55)
    )


def _render(sun: SunTimes, now: datetime, size: tuple[int, int], scale: float) -> Image.Image:
    """Draw into a box with a white frame around it, so ink outside the box is detectable."""
    width, height = size
    image = Image.new("L", (width + 40, height + 40), 255)
    draw_sun_arc(
        ImageDraw.Draw(image), (20, 20, 20 + width, 20 + height), sun, now, TZ, "12h", scale
    )
    return image


@pytest.mark.behaviour
@pytest.mark.parametrize(
    ("size", "scale"), [((600, 260), 1.0), ((560, 170), 0.6), ((300, 120), 0.4)]
)
def test_arc_stays_inside_its_box(sun: SunTimes, size: tuple[int, int], scale: float) -> None:
    image = _render(sun, _at(12, 44), size, scale)
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
def test_sun_is_above_the_horizon_by_day_and_below_by_night(sun: SunTimes) -> None:
    """A filled disc sits on the arc at noon; at night a hollow disc sits under the horizon."""
    noon = _render(sun, _at(13, 23), (600, 260), 1.0)  # solar noon for these sun times
    night = _render(sun, _at(23, 0), (600, 260), 1.0)
    # Column through the centre: by day the topmost ink is the sun disc, high in the box.
    center = noon.width // 2
    top_ink_noon = min(y for y in range(noon.height) if noon.getpixel((center, y)) == 0)
    assert top_ink_noon < 60
    # At night the arc top is unchanged but a hollow disc adds ink below the horizon that
    # noon does not have: compare the lower halves.
    lower = (0, 150, 640, 260)
    noon_dark = noon.crop(lower).histogram()[0]
    night_dark = night.crop(lower).histogram()[0]
    assert night_dark > noon_dark


@pytest.mark.behaviour
def test_twilight_sun_and_degenerate_times_do_not_crash(sun: SunTimes) -> None:
    for moment in (_at(7, 5), _at(19, 45), _at(6, 53), _at(19, 55), _at(0, 0)):
        assert _render(sun, moment, (500, 220), 0.8).getextrema()[0] == 0
    polar = SunTimes(
        civil_dawn=_at(7),
        sunrise=_at(7),
        sunset=_at(7) + timedelta(hours=10),
        civil_dusk=_at(7) + timedelta(hours=10),
    )
    assert _render(polar, _at(12), (500, 220), 0.8).getextrema()[0] == 0


@pytest.mark.behaviour
def test_a_box_too_small_to_draw_in_is_left_blank(sun: SunTimes) -> None:
    image = Image.new("L", (40, 40), 255)
    draw_sun_arc(ImageDraw.Draw(image), (10, 10, 18, 18), sun, _at(12), TZ, "12h", 1.0)
    assert image.getextrema() == (255, 255)


@pytest.mark.behaviour
def test_narrow_box_keeps_sunrise_and_sunset_apart(sun: SunTimes) -> None:
    """In a narrow box the time labels shrink instead of overlapping; dawn/dusk are dropped."""
    image = _render(sun, _at(12), (260, 140), 1.0)
    # The label row: there is a white gap somewhere between the two times.
    row = image.crop((20, 20 + 140 - 60, 280, 20 + 140 - 30))
    columns = [min(row.getpixel((x, y)) for y in range(row.height)) for x in range(row.width)]
    ink = [x for x, v in enumerate(columns) if v < 128]
    assert ink, "no labels drawn"
    gaps = [b - a for a, b in zip(ink, ink[1:], strict=False) if b - a > 12]
    assert gaps, "sunrise and sunset labels run together"


@pytest.mark.behaviour
@pytest.mark.parametrize("size", [(560, 170), (430, 220), (635, 160), (567, 300)])
@pytest.mark.parametrize(
    "offset",
    [timedelta(0), timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=25)],
)
def test_moon_stays_clear_of_the_labels_at_the_edges_of_the_night(
    sun: SunTimes, size: tuple[int, int], offset: timedelta
) -> None:
    """Just after dusk and just before dawn the moon sits near an end of the arc, and at the
    exact instant the sun disc does; a white band separates either from the label row."""
    for moment in (sun.civil_dusk + offset, sun.civil_dawn - offset):
        image = _render(sun, moment, size, 1.0)
        label_top = 20 + size[1] - (sun_arc._LABEL_SIZE + 8) + 4
        band = image.crop((20, label_top - 4, 20 + size[0], label_top))
        assert band.getextrema() == (255, 255), f"ink touches the label row at {moment:%H:%M}"
