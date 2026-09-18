"""User configuration: location, units, and display settings loaded from YAML."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

TemperatureUnit = Literal["celsius", "fahrenheit"]
WindUnit = Literal["kmh", "mph", "ms"]
Orientation = Literal["portrait", "landscape"]
TimeFormat = Literal["12h", "24h"]

#: Kindle Paperwhite 3 native framebuffer size in pixels (portrait), from the device spec.
#: Confirm on the device with ``eips -i`` before relying on it (see docs/DEVICE.md).
PAPERWHITE_3_WIDTH = 1072
PAPERWHITE_3_HEIGHT = 1448


class Location(BaseModel):
    """Where the weather is observed and which clock the dashboard shows.

    Parameters
    ----------
    latitude, longitude
        Decimal degrees, WGS84.
    timezone
        IANA time zone name, for example ``"America/Chicago"``.
    name
        Optional human-readable label some skins display.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    timezone: str
    name: str | None = None

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA time zone: {value!r}") from exc
        return value

    @property
    def tzinfo(self) -> ZoneInfo:
        """The :class:`zoneinfo.ZoneInfo` for :attr:`timezone`."""
        return ZoneInfo(self.timezone)


class Units(BaseModel):
    """Measurement units used by providers and skins."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature: TemperatureUnit = "celsius"
    wind: WindUnit = "kmh"

    @property
    def temperature_symbol(self) -> str:
        """``"°C"`` or ``"°F"``."""
        return "°F" if self.temperature == "fahrenheit" else "°C"


class Display(BaseModel):
    """How the dashboard is laid out and how often the device refreshes it.

    ``width`` and ``height`` are the device's native (portrait) framebuffer size. A
    ``landscape`` orientation, the default, composes on a rotated canvas and rotates the
    result back to native size, so the image always matches the framebuffer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    skin: str = "minimal"
    orientation: Orientation = "landscape"
    width: int = Field(default=PAPERWHITE_3_WIDTH, gt=0)
    height: int = Field(default=PAPERWHITE_3_HEIGHT, gt=0)
    time_format: TimeFormat = "24h"
    refresh_minutes: int = Field(default=15, ge=1)

    @property
    def native_size(self) -> tuple[int, int]:
        """``(width, height)`` of the device framebuffer."""
        return (self.width, self.height)

    @property
    def canvas_size(self) -> tuple[int, int]:
        """Size of the canvas a skin composes on, before rotation to native size."""
        if self.orientation == "landscape":
            return (self.height, self.width)
        return self.native_size


class Settings(BaseModel):
    """Top-level configuration file model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    location: Location
    units: Units = Units()
    display: Display = Display()


def load_settings(path: Path) -> Settings:
    """Load and validate a YAML configuration file.

    Parameters
    ----------
    path
        Path to a YAML file shaped like ``config.example.yaml``.

    Returns
    -------
    Settings
        The validated configuration.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the file is not a YAML mapping or fails validation.
    """
    logger.debug("Loading settings from %s", path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, got {type(raw).__name__}"
        )
    return Settings.model_validate(raw)
