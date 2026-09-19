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
  four-day forecast. Text only; icons are planned. Portrait is a single column;
  landscape is a two-column layout that uses the full width.
- `--orientation` option on `paperwhite render` to override the configured orientation.
- Renderer that composes a skin at the Kindle Paperwhite 3 native size (1072x1448),
  supports portrait and landscape, and quantizes to 16 gray levels.
- `paperwhite` CLI: `render`, `skins`, `providers`, `version`.
- `paperwhite serve` and `service.py`: fetch on a schedule, keep the last good snapshot,
  render frames on request for both orientations, serve `/health`, `/dashboard.png`, and
  `/dashboard/{landscape,portrait}.png` on port 8765. Offline frame before the first fetch.
- `paperwhite serve` reads `PAPERWHITE_CONFIG`, `PAPERWHITE_PROVIDER`, `PAPERWHITE_HOST`,
  and `PAPERWHITE_PORT` from the environment; `/health` reports the server's `hostname`.
- `.env.example` documenting those variables and their built-in defaults
  (`config.yaml` in the working directory, `mock`, `0.0.0.0`, `8765`); the systemd unit
  loads a git-ignored `.env`, a manual `paperwhite serve` does not.
- `deploy/`: systemd user unit (configured through those variables and an optional
  `.env`) and Avahi service file; `docs/DEPLOY.md` with the steps
  verified on the Raspberry Pi.
- Design docs: `docs/ARCHITECTURE.md`, `docs/DEVICE.md`, `docs/ROADMAP.md`.
- `docs/REPOSITORY_STATE.md`: verified repository settings (ruleset, security features, CI)
  with dates and evidence.
- Decision record in `docs/ARCHITECTURE.md`: architecture accepted; landscape default;
  both orientations served; tap to switch orientation; DNS-name discovery on port 8765.
- Jailbreak runbook for the Paperwhite 3 on 5.16.2.1.1 in `docs/DEVICE.md`, with a
  legal and warranty note; executed 2026-09-18/19, with the verified device facts (panel
  1072x1448 8-bit gray, `eips` path, touch node `event1`, RTC `wakealarm`, discovery of
  the Pi by DNS name and the first live frame on the panel).

### Changed
- Default orientation is now `landscape` (was `portrait`).
