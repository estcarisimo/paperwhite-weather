# Changelog

All notable changes to this project are documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org).

## [Unreleased]

### Added
- Project foundation: `src` layout, uv-managed environment, ruff, mypy, pytest, CI, and
  the community files (`AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CITATION.cff`).
- Configuration model (`location`, `units`, `display`) loaded from YAML with strict
  validation, and `config.example.yaml`.
- Provider-independent weather data model (`WeatherSnapshot`) with UTC-aware timestamps.
- `mock` provider with deterministic fixture data for developing skins offline.
- `minimal` skin: large clock and temperature, today's range, sun events, and a
  four-day forecast strip. Text only; icons are planned.
- Renderer that composes a skin at the Kindle Paperwhite 3 native size (1072x1448),
  supports portrait and landscape, and quantizes to 16 gray levels.
- `paperwhite` CLI: `render`, `skins`, `providers`, `version`.
- Design docs: `docs/ARCHITECTURE.md`, `docs/DEVICE.md`, `docs/ROADMAP.md`.
