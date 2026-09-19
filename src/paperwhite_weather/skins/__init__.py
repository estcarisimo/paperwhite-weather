"""Skins: layouts that turn a :class:`WeatherSnapshot` into a grayscale image."""

from __future__ import annotations

from collections.abc import Callable

from paperwhite_weather.skins.base import Skin
from paperwhite_weather.skins.big_clock import BigClockSkin
from paperwhite_weather.skins.forecast import ForecastSkin
from paperwhite_weather.skins.graphic import GraphicSkin
from paperwhite_weather.skins.minimal import MinimalSkin
from paperwhite_weather.skins.newspaper import NewspaperSkin
from paperwhite_weather.skins.weather_station import WeatherStationSkin

_FACTORIES: dict[str, Callable[[], Skin]] = {
    MinimalSkin.name: MinimalSkin,
    NewspaperSkin.name: NewspaperSkin,
    WeatherStationSkin.name: WeatherStationSkin,
    BigClockSkin.name: BigClockSkin,
    ForecastSkin.name: ForecastSkin,
    GraphicSkin.name: GraphicSkin,
}


def available_skins() -> list[str]:
    """Names accepted by :func:`get_skin`, sorted."""
    return sorted(_FACTORIES)


def get_skin(name: str) -> Skin:
    """Instantiate the skin registered under ``name``.

    Raises
    ------
    ValueError
        If no skin has that name. The message lists the available ones.
    """
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(
            f"unknown skin {name!r}; available: {', '.join(available_skins())}"
        ) from None
    return factory()


__all__ = [
    "BigClockSkin",
    "ForecastSkin",
    "GraphicSkin",
    "MinimalSkin",
    "NewspaperSkin",
    "Skin",
    "WeatherStationSkin",
    "available_skins",
    "get_skin",
]
