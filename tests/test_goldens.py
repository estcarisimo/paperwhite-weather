"""Golden-image tests: every skin in both orientations, pinned to `tests/goldens/`."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageChops

from paperwhite_weather.config import Orientation, Settings
from paperwhite_weather.models import WeatherSnapshot
from paperwhite_weather.render import render_dashboard
from paperwhite_weather.skins import available_skins
from tests.conftest import FIXED_NOW

GOLDENS = Path(__file__).parent / "goldens"
ORIENTATIONS: tuple[Orientation, ...] = ("landscape", "portrait")
#: Tolerated fraction of pixels that differ by more than one gray step; guards against a
#: FreeType hinting difference without accepting a layout change.
MAX_DIFFERENT_FRACTION = 0.001


def _cases() -> list[tuple[str, Orientation]]:
    return [(skin, orientation) for skin in available_skins() for orientation in ORIENTATIONS]


@pytest.mark.behaviour
@pytest.mark.parametrize(("skin", "orientation"), _cases())
def test_skin_matches_golden(
    snapshot: WeatherSnapshot, settings: Settings, skin: str, orientation: Orientation
) -> None:
    display = settings.display.model_copy(update={"skin": skin, "orientation": orientation})
    image = render_dashboard(
        snapshot, settings.model_copy(update={"display": display}), now=FIXED_NOW
    )
    golden_path = GOLDENS / f"{skin}-{orientation}.png"
    assert golden_path.exists(), f"missing golden {golden_path.name}; see tests/goldens/README.md"
    with Image.open(golden_path) as golden:
        assert image.size == golden.size and image.mode == golden.mode == "L"
        diff = ImageChops.difference(image, golden.copy())
    # Count pixels differing by more than one quantization step (255/15 = 17).
    different = sum(count for value, count in diff.getcolors(256) or [] if value > 17)
    fraction = different / (image.width * image.height)
    assert fraction <= MAX_DIFFERENT_FRACTION, (
        f"{skin} {orientation}: {fraction:.4%} of pixels differ from the golden; "
        "regenerate on purpose with `paperwhite gallery` (see tests/goldens/README.md)"
    )


def test_every_skin_has_both_goldens() -> None:
    expected = {f"{skin}-{orientation}.png" for skin, orientation in _cases()}
    present = {path.name for path in GOLDENS.glob("*.png")}
    assert present == expected
