from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from paperwhite_weather.config import Display, Location, Settings, load_settings


def test_example_config_loads(settings: Settings) -> None:
    assert settings.location.timezone == "America/Chicago"
    assert settings.units.temperature == "fahrenheit"
    assert settings.display.skin == "minimal"
    assert settings.display.orientation == "landscape"
    assert settings.display.native_size == (1072, 1448)


def test_defaults_are_paperwhite_3_landscape_24h() -> None:
    display = Display()
    assert display.native_size == (1072, 1448)
    assert display.canvas_size == (1448, 1072)
    assert display.orientation == "landscape"
    assert display.time_format == "24h"


def test_portrait_canvas_is_native() -> None:
    display = Display(orientation="portrait")
    assert display.canvas_size == (1072, 1448)
    assert display.native_size == (1072, 1448)


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "", "UTC+3"])
def test_unknown_timezone_is_rejected(timezone: str) -> None:
    with pytest.raises(ValidationError, match="time zone"):
        Location(latitude=0.0, longitude=0.0, timezone=timezone)


@pytest.mark.parametrize(("latitude", "longitude"), [(91.0, 0.0), (0.0, -181.0)])
def test_out_of_range_coordinates_are_rejected(latitude: float, longitude: float) -> None:
    with pytest.raises(ValidationError):
        Location(latitude=latitude, longitude=longitude, timezone="UTC")


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "location:\n  latitude: 0\n  longitude: 0\n  timezone: UTC\n  typo: yes\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="typo"):
        load_settings(path)


def test_non_mapping_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_settings(path)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "nope.yaml")
