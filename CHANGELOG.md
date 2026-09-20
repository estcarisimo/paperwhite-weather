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
- `open-meteo` provider: current conditions, five-day forecast, WMO weather-code mapping,
  configured units; raises `OpenMeteoError` on any transport, HTTP, or shape problem.
  Tested on a recorded response and a local stub server, never against the live API.
- Civil dawn/dusk and sunrise/sunset computed locally with `astral`, pinned to a US Naval
  Observatory table.
- Hourly forecast in the data model (`HourlyForecast`: temperature, condition,
  precipitation probability, wind) from local midnight of today, five days long; the
  `open-meteo` provider requests it and the `mock` provider synthesizes a plausible day.
  The recorded Open-Meteo fixture was refreshed (2026-09-19) to include the hourly block.
- `minimal` skin: large clock and temperature, today's range, the sun arc, and a
  four-day forecast. Portrait is a single column; landscape is a two-column layout that
  uses the full width. Redesigned as the quiet end of the range: the current condition
  as an icon beside the temperature, the range under it, one short sun arc, and the
  next four days as columns (weekday, icon, high and low, a rain drop from 20 % up)
  instead of the bar chart, which stays in `forecast` and `weather-station`. The skin
  now draws on the shared `Canvas` (`Canvas.day_columns` is the new block).
- `graphic` skin, the picture end of the range: a hero of the current condition (large
  icon, the temperature in the Oswald display face), the optional metrics as glyphs
  (thermometer, drops, wind), the sun arc, and the week as a high/low band chart
  (`skins/band_chart.py`: two smooth curves with the band between, values by the dots,
  a rain drop per day, today's temperature as a hollow ring when it has clear room
  from the dots). Shared pieces on the
  canvas: `band_chart()`, `metrics_strip()`, `number()`; glyphs `icons.draw_wind` and
  `icons.draw_thermometer`.
- `timeline` skin, the day hour by hour from the hourly forecast
  (`skins/timeline_chart.py`): a temperature curve with its value every three hours and
  a marker at now, the night shaded, rain probability as a bar per hour, wind as strokes
  that follow the speed, condition icons above every third hour (moon variants after
  sunset), a divider and the weekday at midnight. Portrait shows today midnight to
  midnight with tomorrow as one row; landscape runs into tomorrow's morning with
  tomorrow in the corner. Without hourly data the skin says so instead of a chart.
- Layout pass over three skins: `weather-station` shows the metrics as glyph cells
  (`Canvas.metrics_strip`) instead of a label grid and no longer repeats "Feels like"
  under the temperature, which also uncrowds the arc in landscape; `big-clock` sits the
  clock higher, gives the weather strip and the arc the space below, and writes the
  range as "75° / 57°"; `newspaper` grows the "days ahead" icons to the space left in
  portrait and puts each day's range and condition on their own lines.
- Four more skins, each with portrait and landscape layouts: `newspaper` (serif front
  page), `weather-station` (metrics grid), `big-clock`, and `forecast`. Shared drawing
  helpers in `skins/common.py`; DejaVu Serif bundled alongside DejaVu Sans.
- Monochrome weather icons drawn with Pillow primitives for every condition.
- Typefaces: Inter for text and Oswald for display numerals (SIL OFL), replacing DejaVu
  Sans in every skin; DejaVu Serif stays for `newspaper`.
- Icons redrawn with round-capped strokes and a cleaner cloud; dots for drizzle; moon
  variants for clear and partly cloudy, used for the current condition after sunset.
- Sun arc redrawn: civil twilight as thick gray bands under each end of the horizon, the
  night as a faint dotted half below it with a crescent moon marking the night's progress,
  one label line (sunrise and sunset in bold, dawn and dusk in small gray type between
  them when there is room).
- Temperature bars redrawn: a pale track shows the shared axis, the low and high sit in
  aligned columns either side of it, and the precipitation probability is a drop filled
  to the probability next to the number (`icons.draw_drop`).
- The sun's day as one graphic (`skins/sun_arc.py`): an arc over a horizon line from
  civil dawn to civil dusk, twilight in gray below the line, sunrise and sunset marked and
  labeled, a filled disc where the sun is now (hollow under the horizon at night). Used
  by `minimal`, `weather-station`, `big-clock`, and `forecast` in place of the four
  labeled clocks; `newspaper` keeps its sentence.
- Temperature ranges as bars on one shared scale (`skins/temperature_bars.py`): one row
  per day with the condition icon, a bar from low to high, the values at its ends, the
  precipitation probability in gray, and a disc on today's bar at the current
  temperature. `minimal`, `weather-station`, and `forecast` show today and the next days
  this way instead of "H 75° L 57°" and "66° / 54°" lists; the current-conditions block
  shows the feels-like temperature instead. Narrow boxes give up the notes, then the
  icons, before the bars get too short.
- `paperwhite gallery` renders every skin in both orientations; CI uploads the result.
  Golden-image tests in `tests/goldens/` pin each frame.
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
- `kindle/paperwhite.sh`, the Kindle client: server discovery, fetch, `eips` paint with
  periodic full clears, tap to toggle orientation, stock GUI stopped and restored,
  screensaver and frontlight handled, suspend with an RTC wake between refreshes after a
  tap window, battery level logged per refresh, `enable-boot`/`disable-boot` to start at
  boot through an upstart job; `kindle/config.example`; KUAL extension; a draft USB
  installer. ShellCheck runs on all of it in CI.
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
