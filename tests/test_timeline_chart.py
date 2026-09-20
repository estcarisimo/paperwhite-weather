"""The timeline stays inside its box, marks now, shades the night, and degrades."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.models import Condition, HourlyForecast, SunTimes
from paperwhite_weather.skins.timeline_chart import draw_timeline, hours_from_midnight

TZ = ZoneInfo("America/Chicago")
MIDNIGHT = datetime(2026, 9, 18, 0, 0, tzinfo=TZ)


def _at(hour: int, minute: int = 0) -> datetime:
    return MIDNIGHT + timedelta(hours=hour, minutes=minute)


@pytest.fixture
def sun() -> SunTimes:
    return SunTimes(
        civil_dawn=_at(6, 12), sunrise=_at(6, 40), sunset=_at(19, 5), civil_dusk=_at(19, 33)
    )


def _hours(count: int = 25, sparse: bool = False) -> list[HourlyForecast]:
    return [
        HourlyForecast(
            time=_at(k),
            temperature=57 + 18 * (0.5 - 0.5 * __import__("math").cos((k - 3) / 24 * 6.283)),
            condition=Condition.RAIN if 15 <= k % 24 <= 18 else Condition.PARTLY_CLOUDY,
            precipitation_probability=None if sparse else (60 if 15 <= k % 24 <= 18 else 10),
            wind_speed=None if sparse else 5 + (k % 7),
        )
        for k in range(count)
    ]


def _render(
    hours: list[HourlyForecast],
    now: datetime,
    sun: SunTimes,
    size: tuple[int, int],
    scale: float = 1.0,
    time_format: str = "12h",
) -> Image.Image:
    """Draw into a box with a white frame around it, so ink outside the box is detectable."""
    width, height = size
    image = Image.new("L", (width + 40, height + 40), 255)
    draw_timeline(
        ImageDraw.Draw(image),
        (20, 20, 20 + width, 20 + height),
        hours,
        now,
        sun,
        TZ,
        time_format,
        scale,
    )
    return image


@pytest.mark.behaviour
@pytest.mark.parametrize(
    ("size", "scale", "count"),
    [((944, 560), 1.0, 25), ((1320, 520), 1.0, 36), ((600, 380), 0.6, 25)],
)
def test_timeline_stays_inside_its_box(
    sun: SunTimes, size: tuple[int, int], scale: float, count: int
) -> None:
    image = _render(_hours(count), _at(16, 45), sun, size, scale)
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
def test_now_marker_moves_with_the_time_and_the_night_is_shaded(sun: SunTimes) -> None:
    hours = _hours()
    afternoon = _render(hours, _at(16, 45), sun, (944, 560))
    evening = _render(hours, _at(22, 0), sun, (944, 560))
    assert afternoon.tobytes() != evening.tobytes()
    # A column at 3 AM lies in the night shade; one at noon does not. Probe a row above
    # the curve area, where only the shade can put ink.
    plot_left = 20 + 40
    step = (944 - 40 - 30) / 24
    y = 20 + 56 + 54 - 20
    at_3 = afternoon.getpixel((round(plot_left + 3 * step), y))
    at_noon = afternoon.getpixel((round(plot_left + 12 * step), y))
    assert at_3 < 255 and at_noon == 255


@pytest.mark.behaviour
def test_degrades_with_sparse_hours_and_short_boxes(sun: SunTimes) -> None:
    assert _render(_hours(sparse=True), _at(12), sun, (944, 560)).getextrema()[0] == 0
    assert _render(_hours(2), _at(0, 30), sun, (600, 400)).getextrema()[0] == 0
    assert _render(_hours(1), _at(12), sun, (600, 400)).getextrema() == (255, 255)
    assert _render([], _at(12), sun, (600, 400)).getextrema() == (255, 255)
    assert _render(_hours(), _at(12), sun, (600, 120)).getextrema() == (255, 255)
    flat = [h.model_copy(update={"temperature": 60.0}) for h in _hours()]
    assert _render(flat, _at(12), sun, (944, 560)).getextrema()[0] == 0
    assert _render(_hours(), _at(12), sun, (944, 560), time_format="24h").getextrema()[0] == 0


def test_hours_from_midnight_starts_at_the_local_day() -> None:
    hours = [
        HourlyForecast(time=_at(k) - timedelta(days=1), temperature=10.0, condition=Condition.CLEAR)
        for k in range(48)
    ]
    picked = hours_from_midnight(hours, _at(16, 45), TZ, 25)
    assert len(picked) == 24  # the series ends at 23:00 today
    assert picked[0].time == MIDNIGHT
    assert hours_from_midnight([], _at(16, 45), TZ, 25) == []


@pytest.mark.behaviour
def test_value_labels_sit_clear_of_a_steep_curve(sun: SunTimes) -> None:
    """On a sawtooth series every labeled point has white between the curve and its label."""
    hours = [
        h.model_copy(update={"temperature": 50.0 + (20.0 if k % 6 < 3 else 0.0) + k % 3 * 6})
        for k, h in enumerate(_hours())
    ]
    size = (944, 560)
    image = _render(hours, _at(16, 45), sun, size)
    temperatures = [h.temperature for h in hours]
    lo, hi = min(temperatures), max(temperatures)
    plot_left, step = 20 + 40, (944 - 40 - 30) / 24
    curve_top, curve_bottom = 20 + 56 + 54, 20 + 560 - 44 - 90 - 70 - 30
    for k in range(0, 25, 3):
        x = round(plot_left + step * k)
        y = round(curve_bottom - (temperatures[k] - lo) / (hi - lo) * (curve_bottom - curve_top))
        neighbors = [temperatures[j] for j in (k - 1, k + 1) if 0 <= j < 25]
        direction = -1 if sum(neighbors) / len(neighbors) <= temperatures[k] else 1
        column = [image.getpixel((x, y + direction * d)) for d in range(0, 70)]
        # Leaving the curve there must be a white run before the label's ink.
        first_white = next(d for d, v in enumerate(column) if v == 255)
        text_ink = next((d for d, v in enumerate(column) if d > first_white and v < 128), None)
        assert text_ink is not None, f"no label found at hour {k}"
        assert all(v == 255 for v in column[first_white : first_white + 2]), (
            f"curve touches the label at hour {k}"
        )


@pytest.mark.behaviour
def test_midnight_value_label_is_drawn_over_the_divider(sun: SunTimes) -> None:
    """A 36-hour span has a midnight inside it; the value written there stays readable."""
    hours = _hours(36)
    image = _render(hours, _at(16, 45), sun, (1320, 520))
    temperatures = [h.temperature for h in hours]
    lo, hi = min(temperatures), max(temperatures)
    plot_left, step = 20 + 40, (1320 - 40 - 30) / 35
    curve_top, curve_bottom = 20 + 56 + 54, 20 + 520 - 44 - 90 - 70 - 30
    x = round(plot_left + step * 24)
    y = round(curve_bottom - (temperatures[24] - lo) / (hi - lo) * (curve_bottom - curve_top))
    neighbors = [temperatures[23], temperatures[25]]
    direction = -1 if sum(neighbors) / 2 <= temperatures[24] else 1
    column = [image.getpixel((x, y + direction * d)) for d in range(0, 70)]
    assert 255 in column, "the divider covers the whole column"
    assert any(v == 0 for v in column[column.index(255) :]), "no black label ink over the divider"
