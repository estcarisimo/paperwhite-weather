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
  models.py         WeatherSnapshot, CurrentConditions, DailyForecast, SunTimes, Condition
  units.py          celsius_to_fahrenheit, kmh_to_mph, kmh_to_ms
  fonts.py          load_font(weight, size) from the bundled DejaVu Sans (assets/fonts/)
  providers/        base.py (WeatherProvider protocol), mock.py (fixture data), registry in
                    __init__.py: get_provider(name), available_providers()
  skins/            base.py (Skin protocol, format helpers, CONDITION_LABELS),
                    minimal.py; registry in __init__.py: get_skin(name), available_skins()
  render.py         render_dashboard(snapshot, settings, now) -> "L" image at native size;
                    quantize_grayscale(image, levels)
  cli.py            Typer app: `paperwhite render|skins|providers|version`
tests/              pytest; conftest.py has the example-config and fixed-snapshot fixtures
kindle/             device-side shell scripts (Sprint 3; empty until then)
docs/               ARCHITECTURE.md, DEVICE.md, ROADMAP.md, REPOSITORY_STATE.md
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
  load fonts from the host; use `fonts.load_font`.
- Providers raise on any failure; no partial snapshots, no silent fallbacks. Caching the
  last good snapshot belongs to the (future) service layer, not to providers.
- Tests: plain functions, fixtures, `parametrize`. Markers `math` / `behaviour` as
  defined in `pyproject.toml`; `--strict-markers` is on. `tests/test_<module>.py`
  mirrors `src/`.
- Keep `CHANGELOG.md` current: a bullet under `[Unreleased]` for every user-visible
  change. Version lives only in `pyproject.toml` (and `CITATION.cff` at release time).
- Do not edit `uv.lock` by hand; run `uv lock` / `uv add`. CI uses `uv sync --locked`.
- Never commit a real location, credentials, or rendered PNGs (`.gitignore` covers
  `config.yaml` and `*.png`; reference screenshots go in `docs/img/` deliberately).
- Documented commands are run before they are written down. Kindle-side commands that
  have not been run on the device are labeled **draft** in `docs/DEVICE.md`.

## Things that are easy to get wrong

- The Kindle's framebuffer is portrait (1072x1448). Landscape is a rendering choice:
  compose on 1448x1072, then `render.py` rotates 90° counterclockwise. If the device
  shows it upside down, fix the rotation direction in `render.py`, not in the skins.
- Display width/height are configuration, not constants, so other Kindles can be
  supported later; only the defaults are Paperwhite 3.
- DejaVu Sans is bundled under the Bitstream Vera license
  (`src/paperwhite_weather/assets/fonts/LICENSE-DejaVu.txt`). Adding another typeface
  needs a license check and the license file next to it.
- `MockProvider` builds "today" from the location's local date, not the UTC date.
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
