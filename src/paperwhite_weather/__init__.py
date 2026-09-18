"""Paperwhite Weather: render an e-ink weather dashboard for a repurposed Kindle.

The package fetches weather data through a provider, normalizes it into a
:class:`~paperwhite_weather.models.WeatherSnapshot`, and renders it with a skin into a
grayscale image sized for the Kindle framebuffer. The Kindle itself only downloads and
displays that image.
"""

from importlib.metadata import version

__version__ = version("paperwhite-weather")

__all__ = ["__version__"]
