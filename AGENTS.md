# AGENTS.md — Paperwhite Weather

Instructions for AI coding agents (Claude Code, Codex, Cursor, ...) working in this
repository. `CLAUDE.md` includes this file. Humans: see `CONTRIBUTING.md`.

**Language policy: American English is mandatory** for this file, all agent instructions,
all function, method, variable, and file names, and all documentation and commit messages
(`initialize`, `analyze`, `color`, `behavior`).

## What this project is

Paperwhite Weather turns a used Kindle into a quiet, always-on e-ink home display showing
time, current weather, a multi-day forecast, and sun/twilight times, with interchangeable
skins. The design is client-server: a small Python service (this package) fetches weather,
normalizes it, renders a PNG at the Kindle's native resolution, and serves it on the LAN;
the jailbroken Kindle only downloads the PNG, writes it to the e-ink panel, and sleeps.
`docs/ARCHITECTURE.md` records the decision and its alternatives.

The target device is a **Kindle Paperwhite 3 (7th generation, 2015)** on firmware
5.16.2.1.1; framebuffer 1072x1448, 16 gray levels. `docs/DEVICE.md` lists what has been
verified on the actual device and what is still an assumption.

The distribution is `paperwhite-weather`, the import package `paperwhite_weather`, the
command `paperwhite`. It is **not** on PyPI yet (the name was free on 2026-09-18). Never
write `pip install paperwhite-weather`; install from GitHub, and no PyPI badge until the
first upload.

## Layout

```
src/paperwhite_weather/
  config.py         Pydantic settings: Location, Units, Display, Settings; load_settings(path)
  models.py         WeatherSnapshot, CurrentConditions, DailyForecast, HourlyForecast, SunTimes,
                    Condition
  units.py          celsius_to_fahrenheit, kmh_to_mph, kmh_to_ms
  fonts.py          load_font(weight, size): "regular"/"medium"/"bold" (Inter), "display"
                    (Oswald Medium, condensed numerals), "serif"/"serif-bold" (DejaVu Serif);
                    all bundled in assets/fonts/
  icons.py          draw_icon(draw, condition, box, night): monochrome vector icons, one per
                    Condition, moon variants for clear and partly cloudy at night;
                    draw_drop(draw, box, level): a drop filled to a fraction; draw_wind,
                    draw_thermometer: metric glyphs; Glyph helper
  sun.py            compute_sun_times(location, day) -> SunTimes via astral (civil twilight)
  providers/        base.py (WeatherProvider protocol), mock.py (fixture data),
                    open_meteo.py (live: build_query, parse_forecast, WMO_CONDITIONS,
                    OpenMeteoError), registry in __init__.py: get_provider(name),
                    available_providers()
  skins/            base.py (Skin protocol, format helpers, CONDITION_LABELS), sun_arc.py
                    (draw_sun_arc: the day's arc over a horizon line, sun marked),
                    temperature_bars.py (draw_temperature_bars: days as low-high bars on one
                    axis, today marked), common.py (Canvas: scaled px(), text(), rule(), icon(),
                    sun_arc(), temperature_bars(), band_chart(), day_columns(), metrics_strip(),
                    number(), footer(), metrics()),
                    band_chart.py (draw_band_chart: the week's highs and lows as two curves
                    with the band between), timeline_chart.py (draw_timeline: hours as a
                    temperature curve, rain bars, wind, night shading; hours_from_midnight),
                    minimal.py, newspaper.py, weather_station.py, big_clock.py, forecast.py,
                    graphic.py, timeline.py;
                    registry in __init__.py: get_skin(name), available_skins()
  render.py         render_dashboard(snapshot, settings, now) -> "L" image at native size;
                    render_offline(settings, last_attempt_at, message); quantize_grayscale(image, levels)
  service.py        DashboardService (refresh(), frame(orientation), health()),
                    DashboardServer/DashboardHandler (stdlib http.server), serve_forever()
  cli.py            Typer app: `paperwhite render|gallery|serve|skins|providers|version`
tests/              pytest; conftest.py has the example-config and fixed-snapshot fixtures;
                    fixtures/ holds a recorded Open-Meteo response (metric, Chicago);
                    goldens/ holds one PNG per skin and orientation (see its README)
deploy/             systemd user unit and Avahi service file for the Raspberry Pi
kindle/             paperwhite.sh (client, verified on the device), config.example,
                    extensions/paperwhite (KUAL), install.sh (draft); ShellCheck in CI
docs/               ARCHITECTURE.md, DEVICE.md, DEPLOY.md, ROADMAP.md, REPOSITORY_STATE.md
config.example.yaml Example configuration; real config.yaml is git-ignored
```

## Commands

```bash
uv sync                                     # environment (Python 3.10–3.13 supported)
uv run pre-commit install                   # once per clone
uv run ruff check src/ tests/
uv run ruff format src/ tests/              # CI checks with --check
uv run mypy src/paperwhite_weather          # blocking in CI (disallow_untyped_defs)
uv run pytest --cov=paperwhite_weather      # CI enforces --cov-fail-under=85
uv run paperwhite render --config config.example.yaml --output /tmp/dashboard.png
uv run paperwhite render -c config.example.yaml -o /tmp/d.png --now 2026-09-18T21:45:00+00:00
uv run paperwhite gallery -c config.example.yaml -o tests/goldens --now 2026-09-18T21:45:00+00:00  # regenerate goldens on purpose
uv run paperwhite serve -c config.example.yaml --host 127.0.0.1 --port 18765   # then GET /health
uv build                                    # sdist + wheel via uv_build
```

## Conventions

- Python 3.10+: `X | None`, `list[str]`, no `typing.Optional/List`. Ruff target `py310`.
- Line length 100. Ruff is the only linter/formatter (no black/isort/flake8).
- `pathlib.Path` for paths; `logging` with a module-level logger, never `print`, outside
  `cli.py` (`typer.echo` there).
- NumPy-style docstrings on public API. Type hints on every function.
- All settings live in Pydantic models in `config.py` with `extra="forbid"`; new options
  go there, then `config.example.yaml`, then the CLI, then docs.
- Every `datetime` is timezone-aware. `WeatherSnapshot.fetched_at` is UTC and validated
  as such. Convert to `location.tzinfo` only when formatting.
- Skins receive the canvas size and must return exactly that size in mode `"L"`;
  `render.py` rotates landscape canvases and quantizes to 16 gray levels. Skins never
  load fonts from the host; use `fonts.load_font`. New skins build on `skins/common.py`
  (`Canvas`), branch on `c.landscape` for the two layouts, keep the outer 1.5 % border
  white, cope with every optional field being `None` and with a one-day forecast, and
  register in `skins/__init__.py`. Then regenerate the goldens and add the README row.
- Golden frames in `tests/goldens/` change only on purpose (`paperwhite gallery` with the
  fixed `--now`), with the visual change described in the PR. The test tolerates 0.1 % of
  pixels differing by more than one gray step, no more.
- Icons are drawn, not loaded: `icons.py` maps every `Condition` to a drawer working in a
  unit square; `tests/test_icons.py` checks each stays inside its box at three sizes.
  The sun arc (`skins/sun_arc.py`) and the temperature bars (`skins/temperature_bars.py`)
  are the same idea for the sun times and the forecast: one graphic in a box that stays
  inside it and degrades in narrow boxes (`tests/test_sun_arc.py`,
  `tests/test_temperature_bars.py`).
- Providers raise on any failure; no partial snapshots, no silent fallbacks. Caching the
  last good snapshot is `service.py`'s job, not the providers'.
- Tests never call the real Open-Meteo API: parsing is tested on the recorded fixture and
  the HTTP layer on a local stub server. CI's smoke test uses `--provider mock`. To refresh
  the fixture, run the URL in `tests/fixtures/README.md` and commit the new JSON with the
  date in the filename; update the pinned values in `tests/test_open_meteo.py`.
- Sun times for live providers are computed locally with `astral` (Apache-2.0) via
  `sun.compute_sun_times`, never taken from the API; `MockProvider` keeps its fixed
  fixture times. `tests/test_sun.py` pins them
  to a US Naval Observatory table (`math` marker).
- The service renders on request (clock = request time) and memoizes per minute; it never
  stores rendered files on disk. HTTP is stdlib `http.server`; do not add a web framework
  for four routes.
- The server's hostname is never a constant or a default: clients configure it, `/health`
  reports it, and docs write `<server>`. The maintainer's Pi (`smokingpi`) appears only
  where a verified result is quoted.
- On the maintainer's Pi the service is a user-level systemd unit (`docs/DEPLOY.md`),
  configured through `PAPERWHITE_*` environment variables. After merging a change that
  affects it: `git pull && uv sync && systemctl --user restart paperwhite-weather.service`.
- Tests: plain functions, fixtures, `parametrize`. Markers `math` / `behaviour` as
  defined in `pyproject.toml`; `--strict-markers` is on. `tests/test_<module>.py`
  mirrors `src/`.
- Keep `CHANGELOG.md` current: a bullet under `[Unreleased]` for every user-visible
  change. Version lives only in `pyproject.toml` (and `CITATION.cff` at release time).
- Do not edit `uv.lock` by hand; run `uv lock` / `uv add`. CI uses `uv sync --locked`.
- Never commit a real location, credentials, or rendered PNGs (`.gitignore` covers
  `config.yaml`, `.env`, and `*.png`; reference screenshots go in `docs/img/` deliberately).
  `config.example.yaml` and `.env.example` are the committed templates; a new setting is
  added to the matching template in the same PR.
- Documented commands are run before they are written down. Kindle-side commands that
  have not been run on the device are labeled **draft** in `docs/DEVICE.md`.
- Kindle scripts are POSIX `sh` for BusyBox `ash` (no bashisms; `shellcheck -s sh` in
  CI). Test on the device over SSH (`root@<kindle-ip>`, key auth; find the IP by scanning
  port 22). A synthetic tap is `evemu-event /dev/input/event1 --type EV_KEY --code
  BTN_TOUCH --value 1 --sync` (then `--value 0`); `fbgrab file.png` captures the panel.
  Remember that `stop framework` makes the Kindle's own controls unreachable until `stop`.

## Things that are easy to get wrong

- The Kindle's framebuffer is portrait (1072x1448). Landscape is a rendering choice:
  compose on 1448x1072, then `render.py` rotates 90° counterclockwise. If the device
  shows it upside down, fix the rotation direction in `render.py`, not in the skins.
- Display width/height are configuration, not constants, so other Kindles can be
  supported later; only the defaults are Paperwhite 3.
- Inter and Oswald are bundled as static instances of the Google Fonts variable fonts
  (made with fontTools) under the SIL Open Font License 1.1 (`LICENSE-Inter.txt`,
  `LICENSE-Oswald.txt`); DejaVu Serif under the Bitstream Vera license
  (`LICENSE-DejaVu.txt`), all in `src/paperwhite_weather/assets/fonts/`. Adding another typeface
  needs a license check and the license file next to it.
- `MockProvider` builds "today" from the location's local date, not the UTC date.
- Open-Meteo returns local-time strings without an offset (`2026-09-18T06:33`); the
  daily `time` values are used as dates, the hourly ones are made aware with the
  location's `tzinfo` in `_parse_hourly`, and sun times come from `astral`, so no naive
  datetime ever reaches the model. Hours whose temperature is `null` are dropped. WMO
  codes not in `WMO_CONDITIONS` map to `Condition.UNKNOWN` (shown as a dash), never raise.
- `render_dashboard` verifies the skin's output size and raises; do not catch that.
- The existing Kindle dashboard projects listed in `README.md` are prior art to study,
  not code to copy. Any reuse is an explicit decision recorded in the PR after checking
  the license.

## Pull request workflow (required)

`main` is protected by the `protect-main` ruleset: no direct pushes, PR required, the
`lint`, `test (...)` and `build` checks required, review threads must be resolved.

**Repository policy: every PR gets an independent code review from a fresh session, and
no PR is merged until CI is green and that review returns `APPROVE` on the final
commit.** "Fresh" means a reviewer with no context from the session that wrote the
change: a new AI agent session started for the review alone (a Claude Sonnet subagent
today), or a human. The brief the reviewer follows is `.github/REVIEW.md`; give it the
PR number and nothing else.

The loop:

1. Branch from `main` (`feat/…`, `fix/…`, `docs/…`, `chore/…`), commit, push, open the
   PR with `gh pr create`. Fill the PR template checklist honestly.
2. Wait for CI: `gh pr checks <n> --watch`. If anything is red, read the log
   (`gh run view <run-id> --log-failed`), fix locally, push, wait again.
3. Start a fresh reviewer session with `.github/REVIEW.md` and the PR number. Wait for
   its verdict, then **post the verdict in full as a PR comment**
   (`gh pr comment <n> --body-file <verdict.md>`, prefixed with the round number and
   the commit reviewed). The verdict lives on the PR, not in a session transcript.
4. For each finding either **fix it** (commit + push) or **rebut it with evidence** in a
   PR comment. Reviewers do produce false positives. Pre-existing bugs outside the PR's
   scope go to a GitHub issue, linked from the PR.
5. After any push, start **another** fresh reviewer (never reuse the previous session).
   It reads the earlier rounds (`gh pr view <n> --comments`) and reports any finding
   that was neither fixed nor validly rebutted. Repeat 2–5 until CI is green **and** the
   latest push has `VERDICT: APPROVE`.
6. Only then merge: `gh pr merge <n> --squash`. Never merge red, never merge without an
   `APPROVE` on the final commit. Record the number of review rounds in the session log.
7. Do not use the admin bypass. If a human explicitly asks for it in an emergency, note
   it in the PR description.

Never push directly to `main`, never force-push a shared branch, never disable or weaken
a CI check to get green. One PR at a time when PRs touch `CHANGELOG.md`.

## Session continuity

The roadmap and session log live in the maintainer's Notion page "Paperwhite Weather".
At the start of a session, read the latest log entry there (or ask for it); at the end,
record what was done, what was verified, what is pending, and the next concrete action,
with branch/commit/PR references. `docs/ROADMAP.md` mirrors the sprint plan and is
updated by PR when the plan changes.
