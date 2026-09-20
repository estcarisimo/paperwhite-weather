"""Bundled typefaces so rendering is identical on every machine and in CI.

Inter (text) and Oswald (display numerals) are static instances of the Google Fonts
variable fonts, made with fontTools; both are under the SIL Open Font License 1.1
(``assets/fonts/LICENSE-Inter.txt``, ``assets/fonts/LICENSE-Oswald.txt``). Playfair
Display (the newspaper's display serif) is the unmodified variable font, also under the
OFL (``assets/fonts/LICENSE-Playfair.txt``); its license reserves the family name for
unmodified files, so the weight is chosen at load time instead of being instanced. DejaVu
Serif is redistributed under the Bitstream Vera license (``assets/fonts/LICENSE-DejaVu.txt``).
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import as_file, files
from typing import Literal

from PIL import ImageFont

Weight = Literal["regular", "medium", "bold", "display", "serif", "serif-bold", "serif-display"]

_FILES: dict[Weight, str] = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "bold": "Inter-Bold.ttf",
    "display": "Oswald-Medium.ttf",
    "serif": "DejaVuSerif.ttf",
    "serif-bold": "DejaVuSerif-Bold.ttf",
    "serif-display": "PlayfairDisplay[wght].ttf",
}
#: Variable fonts and the weight-axis value to set after loading.
_VARIATIONS: dict[Weight, float] = {"serif-display": 700.0}


@lru_cache(maxsize=64)
def load_font(weight: Weight, size: int) -> ImageFont.FreeTypeFont:
    """Load a bundled font at ``size`` pixels.

    Parameters
    ----------
    weight
        ``"regular"``, ``"medium"``, ``"bold"`` (Inter), ``"display"`` (Oswald Medium, a
        condensed face for large numerals), ``"serif"``, ``"serif-bold"`` (DejaVu Serif),
        or ``"serif-display"`` (Playfair Display Bold, for mastheads and headlines).
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
        font = ImageFont.truetype(str(path), size)
    if weight in _VARIATIONS:
        font.set_variation_by_axes([_VARIATIONS[weight]])
    return font
