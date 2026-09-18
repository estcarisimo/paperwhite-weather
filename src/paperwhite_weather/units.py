"""Unit conversions shared by providers."""

from __future__ import annotations


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a temperature from degrees Celsius to degrees Fahrenheit."""
    return celsius * 9.0 / 5.0 + 32.0


def kmh_to_mph(kmh: float) -> float:
    """Convert a speed from kilometers per hour to miles per hour."""
    return kmh / 1.609344


def kmh_to_ms(kmh: float) -> float:
    """Convert a speed from kilometers per hour to meters per second."""
    return kmh / 3.6
