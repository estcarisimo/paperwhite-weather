# Contributing to Paperwhite Weather

Thanks for your interest. This guide covers the development setup, the checks every change
must pass, and how a change gets from your machine into `main`. Everything in this
repository is written in American English.

## Development setup

The project uses [uv](https://github.com/astral-sh/uv) for environments, dependencies, and
building. You do not need a Kindle to work on the renderer.

```bash
git clone git@github.com:estcarisimo/paperwhite-weather.git
cd paperwhite-weather
uv sync                       # runtime + dev tools (the `dev` group is installed by default)
uv run pre-commit install     # git hooks: ruff lint/format, file hygiene
```

Run the same checks CI runs:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/paperwhite_weather          # blocking in CI
uv run pytest --cov=paperwhite_weather      # coverage floor enforced in CI
uv run paperwhite render --config config.example.yaml --output /tmp/dashboard.png
uv build
```

`uv run pre-commit run --all-files` runs the lint and hygiene hooks on the whole tree.

## Project conventions

- Python 3.10+ code: `X | None` unions, `list[str]` generics. Ruff's `UP` rules enforce
  the 3.10 target.
- Line length 100, ruff formatter, imports sorted by ruff (`I`). The `ignore` list in
  `[tool.ruff.lint]` names the reason for each entry; do not add entries without one.
- `pathlib.Path` for paths, `logging` (module-level `logger = logging.getLogger(__name__)`)
  instead of `print` in library code. `typer.echo` belongs in `cli.py` only.
- NumPy-style docstrings on public functions and classes. Type hints on every function;
  mypy runs with `disallow_untyped_defs` and is blocking in CI.
- Configuration is Pydantic models in `src/paperwhite_weather/config.py`. Add a field
  there, then thread it through the CLI and `config.example.yaml`.
- Timestamps are timezone-aware; `WeatherSnapshot.fetched_at` is UTC. Convert to the
  location's time zone only when formatting.
- Skins compose on the canvas size they are given and must return exactly that size; the
  renderer handles rotation and quantization. New skins register in
  `src/paperwhite_weather/skins/__init__.py`.
- Providers raise on failure instead of returning partial data. New providers register in
  `src/paperwhite_weather/providers/__init__.py` and get a test with a recorded response.
- Tests are plain pytest functions with fixtures and `parametrize`, one file per module.
  Every test carries the `math` marker (checked against an independent computation) or the
  `behaviour` marker (pins current behavior), or neither when it is a plain contract test.
- Golden images, when introduced, change only on purpose, with a before/after comparison
  in the PR description.
- Never commit a real location, credentials, or rendered dashboards. `config.yaml` and
  `*.png` are git-ignored; reference screenshots live in `docs/img/` by explicit exception.
- Every behavior change gets a test and a line in `CHANGELOG.md` under `[Unreleased]`.

## Making a change

`main` is protected. Nobody pushes to it directly; every change lands through a pull
request that has passed CI **and** an independent code review from a fresh session (see
`.github/REVIEW.md`). A PR without an `APPROVE` on its final commit is not merged.

1. Create a branch from `main`: `git switch -c <type>/<short-name>` (`feat/`, `fix/`,
   `docs/`, `chore/`).
2. Commit in small, coherent steps. The pre-commit hooks run ruff on each commit.
3. Push and open a PR: `gh pr create --fill`. The PR template has a checklist.
4. **Iterate until green.** Two things must be true before merging:
   - CI is green: `lint`, every `test (...)` matrix leg, and `build`.
   - A reviewer with no context from your session (a new AI agent session given only
     `.github/REVIEW.md` and the PR number, or a human) has returned `VERDICT: APPROVE`
     for the **latest** push. Every finding before that is either fixed or rebutted with
     evidence in the PR; after each push, start a new reviewer session.

   ```bash
   gh pr checks <n> --watch          # wait for CI
   gh pr view <n> --comments         # every round's verdict is posted here in full
   ```

5. Merge (squash) once both are green. The branch is deleted automatically.

Open one PR at a time when PRs touch `CHANGELOG.md`; parallel PRs spend their review
rounds on merge conflicts.

Repository admins can technically bypass the ruleset. Treat that as an emergency-only
escape hatch and say so in the PR when it is used.

## Documentation site

The `docs/` folder is also the MkDocs site published at
https://estcarisimo.github.io/paperwhite-weather/. `uv sync --group docs`, then
`uv run mkdocs serve` to preview and `uv run mkdocs build --strict` to check; CI runs the
strict build on every pull request and deploys from `main`. A new page goes into `nav` in
`mkdocs.yml`.

## Working on the Kindle side

Scripts under `kindle/` run as root on a jailbroken device. Test them on the device before
documenting them; a command that has not been run on hardware is labeled as a draft.
`docs/DEVICE.md` records what has been verified and how.

## Releasing

1. Bump `version` in `pyproject.toml` (the only place the version lives;
   `paperwhite_weather.__version__` reads it from package metadata).
2. Move the `[Unreleased]` section of `CHANGELOG.md` under a new `[X.Y.Z] - YYYY-MM-DD`
   heading. Update `version` and `date-released` in `CITATION.cff` and validate it with
   `uvx cffconvert --validate`.
3. Open a PR with those changes and merge it.
4. Tag and publish a GitHub release: `git tag vX.Y.Z && git push origin vX.Y.Z`, then
   `gh release create vX.Y.Z --generate-notes`.

The project is not published to PyPI or any other package index, by decision; it is
installed from GitHub. Do not add a PyPI badge or `pip install` instructions.

## Reporting issues

Use the issue templates. For security problems follow `SECURITY.md` instead of opening a
public issue.
