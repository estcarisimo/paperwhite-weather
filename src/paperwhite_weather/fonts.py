"""Bundled typefaces so rendering is identical on every machine and in CI.

DejaVu Sans is redistributed under the Bitstream Vera license; see
``assets/fonts/LICENSE-DejaVu.txt``.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import as_file, files
from typing import Literal

from PIL import ImageFont

Weight = Literal["regular", "bold"]

_FILES: dict[Weight, str] = {
    "regular": "DejaVuSans.ttf",
    "bold": "DejaVuSans-Bold.ttf",
}


@lru_cache(maxsize=64)
def load_font(weight: Weight, size: int) -> ImageFont.FreeTypeFont:
    """Load a bundled font at ``size`` pixels.

    Parameters
    ----------
    weight
        ``"regular"`` or ``"bold"``.
    size
        Font size in pixels; must be positive.

    Returns
    -------
    PIL.ImageFont.FreeTypeFont
    """
    if size <= 0:
        raise ValueError(f"font size must be positive, got {size}")
    resource = files("paperwhite_weather.assets.fonts").joinpath(_FILES[weight])
    with as_file(resource) as path:
        return ImageFont.truetype(str(path), size)
