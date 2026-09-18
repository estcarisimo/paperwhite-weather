from __future__ import annotations

from datetime import datetime, timezone

import pytest
from PIL import Image, ImageDraw

from paperwhite_weather.config import Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.render import EINK_GRAY_LEVELS, quantize_grayscale, render_dashboard
from paperwhite_weather.skins import available_skins, get_skin
from paperwhite_weather.skins.base import fit_font, format_clock, format_temperature
from tests.conftest import FIXED_NOW


def _gray_levels(image: Image.Image) -> set[int]:
    return {value for _count, value in image.getcolors(256) or []}


def test_registry_lists_minimal() -> None:
    assert available_skins() == ["minimal"]
    assert get_skin("minimal").name == "minimal"
    with pytest.raises(ValueError, match="available: minimal"):
        get_skin("nope")


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_render_matches_native_size_in_both_orientations(
    snapshot: WeatherSnapshot, settings: Settings, orientation: str
) -> None:
    settings = settings.model_copy(
        update={"display": settings.display.model_copy(update={"orientation": orientation})}
    )
    image = render_dashboard(snapshot, settings, now=FIXED_NOW)
    assert image.mode == "L"
    assert image.size == settings.display.native_size == (1072, 1448)


def test_render_draws_ink_and_quantizes(snapshot: WeatherSnapshot, settings: Settings) -> None:
    image = render_dashboard(snapshot, settings, now=FIXED_NOW)
    levels = _gray_levels(image)
    assert 0 in levels, "no black pixels: nothing was drawn"
    assert 255 in levels, "no white pixels: background missing"
    assert len(levels) <= EINK_GRAY_LEVELS


def test_render_is_deterministic(snapshot: WeatherSnapshot, settings: Settings) -> None:
    first = render_dashboard(snapshot, settings, now=FIXED_NOW)
    second = render_dashboard(snapshot, settings, now=FIXED_NOW)
    assert first.tobytes() == second.tobytes()


def test_render_rejects_naive_now(snapshot: WeatherSnapshot, settings: Settings) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        render_dashboard(snapshot, settings, now=datetime(2026, 9, 18, 21, 45))


def test_render_defaults_to_current_time(snapshot: WeatherSnapshot, settings: Settings) -> None:
    image = render_dashboard(snapshot, settings)
    assert image.size == (1072, 1448)


def test_render_rejects_wrong_sized_skin_output(
    snapshot: WeatherSnapshot, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BadSkin:
        name = "bad"

        def compose(self, *args: object, **kwargs: object) -> Image.Image:
            return Image.new("L", (10, 10), 255)

    monkeypatch.setattr("paperwhite_weather.render.get_skin", lambda name: BadSkin())
    with pytest.raises(ValueError, match="expected"):
        render_dashboard(snapshot, settings, now=FIXED_NOW)


def test_quantize_grayscale_levels() -> None:
    gradient = Image.linear_gradient("L")  # 256x256, every value 0..255
    quantized = quantize_grayscale(gradient, levels=16)
    levels = _gray_levels(quantized)
    assert len(levels) == 16
    assert min(levels) == 0 and max(levels) == 255
    assert quantize_grayscale(gradient, levels=2).getcolors() is not None
    with pytest.raises(ValueError, match="between 2 and 256"):
        quantize_grayscale(gradient, levels=1)
    with pytest.raises(ValueError, match="'L' image"):
        quantize_grayscale(gradient.convert("RGB"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(21.4, "21°"), (21.5, "22°"), (-0.4, "0°"), (69.8, "70°")],
)
def test_format_temperature(value: float, expected: str) -> None:
    assert format_temperature(value) == expected


@pytest.mark.parametrize(
    ("hour", "minute", "twelve", "twenty_four"),
    [(0, 5, "12:05 AM", "00:05"), (12, 0, "12:00 PM", "12:00"), (21, 45, "9:45 PM", "21:45")],
)
def test_format_clock(hour: int, minute: int, twelve: str, twenty_four: str) -> None:
    moment = datetime(2026, 9, 18, hour, minute, tzinfo=timezone.utc)
    assert format_clock(moment, "12h") == twelve
    assert format_clock(moment, "24h") == twenty_four


def test_fit_font_shrinks_until_text_fits() -> None:
    draw = ImageDraw.Draw(Image.new("L", (10, 10), 255))
    text = "4:45 PM"
    wide = fit_font(draw, text, "bold", max_size=230, max_width=10_000)
    narrow = fit_font(draw, text, "bold", max_size=230, max_width=400)
    assert wide.size == 230
    assert narrow.size < 230
    assert draw.textlength(text, font=narrow) <= 400
    floor = fit_font(draw, "x" * 500, "regular", max_size=40, max_width=1, min_size=8)
    assert floor.size == 8


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_minimal_skin_keeps_margins_clear(
    snapshot: WeatherSnapshot, settings: Settings, orientation: str
) -> None:
    """No text may run off the canvas: the outer 2% border on every side stays white."""
    display = settings.display.model_copy(update={"orientation": orientation, "time_format": "12h"})
    settings = settings.model_copy(update={"display": display})
    width, height = display.canvas_size
    image = get_skin("minimal").compose(snapshot, settings, FIXED_NOW, (width, height))
    border = round(0.02 * min(width, height))
    for box in (
        (0, 0, width, border),
        (0, height - border, width, height),
        (0, 0, border, height),
        (width - border, 0, width, height),
    ):
        assert image.crop(box).getextrema() == (255, 255), f"ink in border {box} ({orientation})"


def test_minimal_landscape_is_two_columns(snapshot: WeatherSnapshot, settings: Settings) -> None:
    """A vertical gutter of white separates the two landscape columns.

    The pre-existing single-column layout scaled to landscape ran the clock and the
    temperature line across the whole width, so no full-height white gutter existed; this
    fails on that renderer.
    """
    display = settings.display.model_copy(update={"orientation": "landscape"})
    settings = settings.model_copy(update={"display": display})
    width, height = display.canvas_size
    image = get_skin("minimal").compose(snapshot, settings, FIXED_NOW, (width, height))
    # Gutter position mirrors MinimalSkin.compose_landscape: margin + 56% of the content
    # width; probe a narrow strip there over the top 85% of the canvas (above the footer).
    margin = round(0.06 * min(width, height))
    gutter = round(60 * min(width / 1448, height / 1072))
    left_width = round((width - 2 * margin - gutter) * 0.56)
    x = margin + left_width + gutter // 2
    strip = image.crop((x - 4, 0, x + 4, round(height * 0.85)))
    assert strip.getextrema() == (255, 255), "ink found in the gutter between the two columns"
    left = image.crop((0, 0, x, round(height * 0.85)))
    right = image.crop((x, 0, width, round(height * 0.85)))
    assert left.getextrema()[0] == 0 and right.getextrema()[0] == 0, "both columns carry ink"


@pytest.mark.behaviour
def test_minimal_skin_handles_a_single_day_forecast(
    snapshot: WeatherSnapshot, settings: Settings
) -> None:
    """Characterization test: a one-day forecast renders in both layouts without error.

    Not a regression guard for a specific change; it pins that the forecast block is
    optional for every layout the skin has.
    """
    only_today = snapshot.model_copy(update={"daily": snapshot.daily[:1]})
    for orientation in ("portrait", "landscape"):
        display = settings.display.model_copy(update={"orientation": orientation})
        size = display.canvas_size
        image = get_skin("minimal").compose(
            only_today, settings.model_copy(update={"display": display}), FIXED_NOW, size
        )
        assert image.size == size
