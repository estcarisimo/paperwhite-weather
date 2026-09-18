"""Skins: layouts that turn a :class:`WeatherSnapshot` into a grayscale image."""

from __future__ import annotations

from collections.abc import Callable

from paperwhite_weather.skins.base import Skin
from paperwhite_weather.skins.minimal import MinimalSkin

_FACTORIES: dict[str, Callable[[], Skin]] = {
    MinimalSkin.name: MinimalSkin,
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


__all__ = ["MinimalSkin", "Skin", "available_skins", "get_skin"]
