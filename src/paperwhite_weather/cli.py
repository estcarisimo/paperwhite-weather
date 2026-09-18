"""Command-line interface: ``paperwhite render|skins|providers|version``."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import typer

from paperwhite_weather import __version__
from paperwhite_weather.config import load_settings
from paperwhite_weather.providers import MockProvider, available_providers, get_provider
from paperwhite_weather.render import render_dashboard
from paperwhite_weather.service import DEFAULT_HOST, DEFAULT_PORT, serve_forever
from paperwhite_weather.skins import available_skins

app = typer.Typer(
    help="Render an e-ink weather dashboard for a repurposed Kindle.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _configure_logging(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logging."),
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def render(
    config: Path = typer.Option(..., "--config", "-c", exists=True, dir_okay=False),
    output: Path = typer.Option(..., "--output", "-o", help="Where to write the PNG."),
    provider: str = typer.Option("mock", "--provider", "-p", help="Weather provider name."),
    skin: str | None = typer.Option(None, "--skin", "-s", help="Override display.skin."),
    orientation: str | None = typer.Option(
        None, "--orientation", help="Override display.orientation (landscape | portrait)."
    ),
    now: datetime | None = typer.Option(
        None,
        "--now",
        help="Timezone-aware ISO 8601 time for the clock (default: current time).",
        formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z"],
    ),
) -> None:
    """Fetch weather with PROVIDER and render one dashboard frame to OUTPUT."""
    settings = load_settings(config)
    overrides = {
        key: value
        for key, value in (("skin", skin), ("orientation", orientation))
        if value is not None
    }
    if overrides:
        # Re-validate so an unknown orientation fails the same way it would in the file.
        display = settings.display.model_validate(settings.display.model_dump() | overrides)
        settings = settings.model_copy(update={"display": display})
    # The mock provider takes the pinned time too, so a fixed --now gives a reproducible frame.
    source = MockProvider(now=now) if provider == MockProvider.name else get_provider(provider)
    weather = source.fetch(settings.location, settings.units)
    image = render_dashboard(weather, settings, now=now)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    width, height = image.size
    typer.echo(
        f"Rendered skin {settings.display.skin!r} ({settings.display.orientation}, "
        f"{width}x{height}) from {weather.source!r} data fetched at "
        f"{weather.fetched_at:%Y-%m-%d %H:%M} UTC -> {output}"
    )


@app.command()
def serve(
    config: Path = typer.Option(..., "--config", "-c", exists=True, dir_okay=False),
    provider: str = typer.Option("mock", "--provider", "-p", help="Weather provider name."),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Interface to listen on."),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="TCP port to listen on."),
) -> None:
    """Fetch weather on a schedule and serve dashboard frames over HTTP on the LAN."""
    settings = load_settings(config)
    serve_forever(settings, get_provider(provider), host=host, port=port)


@app.command()
def skins() -> None:
    """List available skins."""
    for name in available_skins():
        typer.echo(name)


@app.command()
def providers() -> None:
    """List available weather providers."""
    for name in available_providers():
        typer.echo(name)


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(f"paperwhite-weather {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
