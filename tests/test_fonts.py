"""Bundled fonts load at any size; weights differ."""

from __future__ import annotations

from paperwhite_weather.fonts import load_font


def test_serif_display_is_the_bold_instance_of_playfair() -> None:
    """The variable font is loaded with its weight axis at 700, so it renders bold."""
    from PIL import Image, ImageDraw

    def ink(weight: str) -> int:
        image = Image.new("L", (400, 120), 255)
        ImageDraw.Draw(image).text((10, 10), "CHICAGO", font=load_font(weight, 80), fill=0)  # type: ignore[arg-type]
        return image.histogram()[0]

    display = load_font("serif-display", 40)
    assert "Playfair" in display.getname()[0]
    assert display.get_variation_axes()[0]["name"] in (b"Weight", "Weight")
    assert ink("serif-display") > ink("serif") * 1.2  # heavier than the regular serif
