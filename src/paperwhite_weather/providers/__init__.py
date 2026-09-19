"""Weather providers: anything that can produce a :class:`WeatherSnapshot`."""

from __future__ import annotations

from collections.abc import Callable

from paperwhite_weather.providers.base import WeatherProvider
from paperwhite_weather.providers.mock import MockProvider
from paperwhite_weather.providers.open_meteo import OpenMeteoProvider

_FACTORIES: dict[str, Callable[[], WeatherProvider]] = {
    MockProvider.name: MockProvider,
    OpenMeteoProvider.name: OpenMeteoProvider,
}


def available_providers() -> list[str]:
    """Names accepted by :func:`get_provider`, sorted."""
    return sorted(_FACTORIES)


def get_provider(name: str) -> WeatherProvider:
    """Instantiate the provider registered under ``name``.

    Raises
    ------
    ValueError
        If no provider has that name. The message lists the available ones.
    """
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(
            f"unknown provider {name!r}; available: {', '.join(available_providers())}"
        ) from None
    return factory()


__all__ = [
    "MockProvider",
    "OpenMeteoProvider",
    "WeatherProvider",
    "available_providers",
    "get_provider",
]
