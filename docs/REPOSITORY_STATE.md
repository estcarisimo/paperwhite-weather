# Repository state

Verified facts about the GitHub repository, each with the date and the command that showed
it. Anything that could not be verified, or that needs permissions the maintainer does not
have, is listed as **blocked**. Re-verify and update this file when settings change.

All checks below were run by the repository owner (admin) on **2026-09-18**.

## Branch protection

| Setting | State | Evidence |
| --- | --- | --- |
| Ruleset `protect-main` (id 23682025) | active on the default branch | `gh api repos/estcarisimo/paperwhite-weather/rulesets` |
| Rules | deletion blocked, force-push blocked, PR required, review threads must be resolved, squash merge only | `gh api repos/estcarisimo/paperwhite-weather/rules/branches/main` |
| Required status checks (strict, branch up to date) | `lint`, `test (ubuntu-latest, 3.10)`, `test (ubuntu-latest, 3.11)`, `test (ubuntu-latest, 3.12)`, `test (ubuntu-latest, 3.13)`, `test (macos-latest, 3.12)`, `build` | same ruleset |
| Bypass | Repository admin only (policy: emergencies, noted in the PR) | same ruleset |
| Merge methods | squash only | `gh api repos/estcarisimo/paperwhite-weather --jq '.allow_squash_merge, .allow_merge_commit, .allow_rebase_merge'` |
| Delete branch on merge | enabled | `gh api repos/estcarisimo/paperwhite-weather --jq .delete_branch_on_merge` |

The bootstrap commit (`d818683`) was pushed to `main` before the ruleset existed. Every
change since goes through a pull request.

## Security features

| Feature | State | Evidence |
| --- | --- | --- |
| Private vulnerability reporting | enabled | `gh api repos/estcarisimo/paperwhite-weather/private-vulnerability-reporting` → `{"enabled":true}` |
| Secret scanning | enabled | `gh api repos/estcarisimo/paperwhite-weather --jq .security_and_analysis` |
| Secret scanning push protection | enabled | same |
| Dependabot alerts | enabled | `gh api -X PUT .../vulnerability-alerts` → 204 |
| Dependabot security updates | enabled | `.security_and_analysis.dependabot_security_updates` |
| Dependabot version updates | configured (`.github/dependabot.yml`: uv + GitHub Actions, weekly, grouped) | file in repo |
| CodeQL code scanning | default setup configured, languages `python` and `actions`, weekly schedule; setup run succeeded | `gh api repos/estcarisimo/paperwhite-weather/code-scanning/default-setup` |
| Open alerts (Dependabot / code scanning / secret scanning) | 0 / 0 / 0 | `gh api ".../{dependabot,code-scanning,secret-scanning}/alerts?state=open"` |
| Static checks in CI | bandit and pip-audit on every PR | `.github/workflows/ci.yml` |

The `SECURITY.md` link to `security/advisories/new` is the standard private-report URL for a
repository with private vulnerability reporting enabled. It has not been exercised with a test
report, on purpose. No email address appears in the repository; contact paths are GitHub-only
(decision of 2026-09-20).

## Community profile

| Item | State |
| --- | --- |
| Health percentage | 100 % (`gh api repos/estcarisimo/paperwhite-weather/community/profile`) |
| Files | `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`, `CHANGELOG.md`, `AGENTS.md` + `CLAUDE.md`, `CODEOWNERS`, issue forms, PR template |

## CI

| Item | State | Evidence |
| --- | --- | --- |
| First CI run on `main` | all 7 jobs green | https://github.com/estcarisimo/paperwhite-weather/actions/runs/35395063223 |
| Coverage floor | 85 % (`--cov-fail-under=85`); measured 99 % locally on 2026-09-18 | `uv run pytest --cov=paperwhite_weather` |
| Actions pinned to commit SHAs | yes (`actions/checkout`, `astral-sh/setup-uv`, `actions/upload-artifact`) | `.github/workflows/ci.yml` |
| Workflow permissions | `contents: read` | `.github/workflows/ci.yml` |
| GitHub Pages | enabled 2026-09-20 with `build_type: workflow` (deploys from Actions, no `gh-pages` branch); site https://estcarisimo.github.io/paperwhite-weather/ | `gh api -X POST repos/estcarisimo/paperwhite-weather/pages -f build_type=workflow`; `.github/workflows/docs.yml` (`pages: write`, `id-token: write` on the deploy job only) |

## Package name

| Item | State | Evidence |
| --- | --- | --- |
| `paperwhite-weather` on PyPI | not registered (free) | `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/paperwhite-weather/json` → 404 |
| `paperwhite-weather` on TestPyPI | not registered (free) | same against `test.pypi.org` → 404 |
| GitHub release | `v0.1.0` published 2026-09-20, marked latest (`gh release view v0.1.0`) | https://github.com/estcarisimo/paperwhite-weather/releases/tag/v0.1.0 |
| Publication | **none, by decision (2026-09-20)**: the project is installed from GitHub and is not published to PyPI or any other package index; no Trusted Publishing | maintainer's decision |

## Re-verified on 2026-09-20 (Sprint 5)

| Item | State | Evidence |
| --- | --- | --- |
| `CITATION.cff` | valid | `uvx cffconvert --validate` → "Citation metadata are valid according to schema version 1.2.0" |
| Private vulnerability reporting | enabled | `gh api repos/estcarisimo/paperwhite-weather/private-vulnerability-reporting` → `{"enabled":true}` |
| `SECURITY.md` report link | resolves | `curl -o /dev/null -w '%{http_code} %{redirect_url}' .../security/advisories/new` → `302` to `github.com/login?return_to=…/security/advisories/new` (the form needs a GitHub login); `.../security/advisories` and `.../security` → 200 |
| Secret scanning, push protection, Dependabot security updates | enabled | `gh api repos/estcarisimo/paperwhite-weather --jq .security_and_analysis` |
| Open alerts (Dependabot / code scanning / secret scanning) | 0 / 0 / 0 | `gh api ".../{dependabot,code-scanning,secret-scanning}/alerts?state=open"` |

## Blocked or pending

- Nothing is blocked on permissions: the maintainer is the repository admin.
- `CITATION.cff` re-validated on 2026-09-20 with `date-released: "2026-09-20"` for 0.1.0
  (`uvx cffconvert --validate` → valid, schema 1.2.0).
