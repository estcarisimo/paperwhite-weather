"""Bundled typefaces so rendering is identical on every machine and in CI.

Inter (text) and Oswald (display numerals) are static instances of the Google Fonts
variable fonts, made with fontTools; both are under the SIL Open Font License 1.1
(``assets/fonts/LICENSE-Inter.txt``, ``assets/fonts/LICENSE-Oswald.txt``). DejaVu Serif
is redistributed under the Bitstream Vera license (``assets/fonts/LICENSE-DejaVu.txt``).
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import as_file, files
from typing import Literal

from PIL import ImageFont

Weight = Literal["regular", "medium", "bold", "display", "serif", "serif-bold"]

_FILES: dict[Weight, str] = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "bold": "Inter-Bold.ttf",
    "display": "Oswald-Medium.ttf",
    "serif": "DejaVuSerif.ttf",
    "serif-bold": "DejaVuSerif-Bold.ttf",
}


@lru_cache(maxsize=64)
def load_font(weight: Weight, size: int) -> ImageFont.FreeTypeFont:
    """Load a bundled font at ``size`` pixels.

    Parameters
    ----------
    weight
        ``"regular"``, ``"medium"``, ``"bold"`` (Inter), ``"display"`` (Oswald Medium, a
        condensed face for large numerals), ``"serif"``, or ``"serif-bold"`` (DejaVu
        Serif).
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
