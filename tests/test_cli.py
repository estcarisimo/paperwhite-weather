from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from paperwhite_weather import __version__
from paperwhite_weather.cli import app
from tests.conftest import EXAMPLE_CONFIG

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"paperwhite-weather {__version__}"


def test_lists() -> None:
    assert runner.invoke(app, ["skins"]).output.split() == [
        "big-clock",
        "forecast",
        "graphic",
        "minimal",
        "newspaper",
        "timeline",
        "weather-station",
    ]
    assert runner.invoke(app, ["providers"]).output.split() == ["mock", "open-meteo"]


def test_render_writes_native_size_png(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "dashboard.png"
    result = runner.invoke(
        app,
        [
            "render",
            "--config",
            str(EXAMPLE_CONFIG),
            "--output",
            str(output),
            "--now",
            "2026-09-18T21:45:00+00:00",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Rendered skin 'minimal' (landscape, 1072x1448)" in result.output
    assert "fetched at 2026-09-18 21:45 UTC" in result.output  # mock honors --now
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.size == (1072, 1448)
        assert image.mode == "L"


def test_render_skin_override_reports_unknown_skin(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["render", "-c", str(EXAMPLE_CONFIG), "-o", str(tmp_path / "x.png"), "--skin", "nope"],
    )
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "available: big-clock" in str(result.exception)


def test_render_unknown_provider_fails(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["render", "-c", str(EXAMPLE_CONFIG), "-o", str(tmp_path / "x.png"), "-p", "nope"]
    )
    assert result.exit_code != 0
    assert "available: mock, open-meteo" in str(result.exception)


def test_render_orientation_override(tmp_path: Path) -> None:
    output = tmp_path / "portrait.png"
    result = runner.invoke(
        app,
        ["render", "-c", str(EXAMPLE_CONFIG), "-o", str(output), "--orientation", "portrait"],
    )
    assert result.exit_code == 0, result.output
    assert "(portrait, 1072x1448)" in result.output

    result = runner.invoke(
        app,
        ["render", "-c", str(EXAMPLE_CONFIG), "-o", str(output), "--orientation", "sideways"],
    )
    assert result.exit_code != 0
    assert "orientation" in str(result.exception)


def test_serve_reads_settings_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The systemd unit configures `serve` through PAPERWHITE_* variables."""
    captured: dict[str, object] = {}

    def fake_serve_forever(settings: object, provider: object, host: str, port: int) -> None:
        captured.update(settings=settings, provider=provider, host=host, port=port)

    monkeypatch.setattr("paperwhite_weather.cli.serve_forever", fake_serve_forever)
    monkeypatch.setenv("PAPERWHITE_CONFIG", str(EXAMPLE_CONFIG))
    monkeypatch.setenv("PAPERWHITE_PROVIDER", "mock")
    monkeypatch.setenv("PAPERWHITE_HOST", "127.0.0.1")
    monkeypatch.setenv("PAPERWHITE_PORT", "28765")
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    assert captured["host"] == "127.0.0.1" and captured["port"] == 28765
    assert getattr(captured["provider"], "name", None) == "mock"

    result = runner.invoke(app, ["serve", "--port", "28766"])
    assert result.exit_code == 0 and captured["port"] == 28766, "flags override the environment"


def test_env_example_matches_the_serve_options() -> None:
    """`.env.example` lists every PAPERWHITE_* variable `serve` reads, with the real default."""
    from paperwhite_weather.cli import serve
    from paperwhite_weather.service import DEFAULT_CONFIG, DEFAULT_HOST, DEFAULT_PORT

    text = (EXAMPLE_CONFIG.parent / ".env.example").read_text(encoding="utf-8")
    documented = dict(
        line.split("=", 1) for line in text.splitlines() if line and not line.startswith("#")
    )
    accepted = {info.envvar for info in serve.__defaults__ or () if getattr(info, "envvar", None)}
    assert (
        set(documented)
        == accepted
        == {
            "PAPERWHITE_CONFIG",
            "PAPERWHITE_PROVIDER",
            "PAPERWHITE_HOST",
            "PAPERWHITE_PORT",
        }
    )
    assert Path(documented["PAPERWHITE_CONFIG"]) == DEFAULT_CONFIG
    assert documented["PAPERWHITE_HOST"] == DEFAULT_HOST
    assert int(documented["PAPERWHITE_PORT"]) == DEFAULT_PORT
    assert documented["PAPERWHITE_PROVIDER"] == "mock"


def test_serve_defaults_to_config_yaml_in_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "paperwhite_weather.cli.serve_forever",
        lambda settings, provider, host, port: captured.update(settings=settings),
    )
    monkeypatch.delenv("PAPERWHITE_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["serve"])
    assert result.exit_code != 0 and "config.yaml" in result.output, "missing file is reported"

    (tmp_path / "config.yaml").write_text(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    assert captured["settings"] is not None


def test_gallery_renders_every_skin_in_both_orientations(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "gallery",
            "-c",
            str(EXAMPLE_CONFIG),
            "-o",
            str(tmp_path / "g"),
            "--now",
            "2026-09-18T21:45:00+00:00",
        ],
    )
    assert result.exit_code == 0, result.output
    files = sorted(p.name for p in (tmp_path / "g").glob("*.png"))
    assert len(files) == 14 and "newspaper-landscape.png" in files
    with Image.open(tmp_path / "g" / "big-clock-portrait.png") as image:
        assert image.size == (1072, 1448)
