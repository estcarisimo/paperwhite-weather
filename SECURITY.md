# Security Policy

## Supported versions

Paperwhite Weather is a hobby project maintained on a best-effort basis. Only the latest
release line receives fixes.

| Version | Supported |
| ------- | --------- |
| 0.x     | ✅        |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Use GitHub's private reporting:
[Report a vulnerability](https://github.com/estcarisimo/paperwhite-weather/security/advisories/new)
(it needs a GitHub account). If you cannot use it, open an issue that says only that you
have a security report and how the maintainer can reach you privately; keep the details
out of the issue.

Include a description of the issue, reproduction steps (a minimal configuration file and
the command that triggers it, with your coordinates removed), and the version and
platform you saw it on. Expect an acknowledgement within about two weeks.

Confirmed vulnerabilities are fixed in a pull request, released, and then disclosed in
`CHANGELOG.md` under *Security* and in a GitHub security advisory that credits the
reporter (unless they prefer otherwise). Reporters are asked to keep details private
until the fix is released.

## What this software does with your data

The dashboard service reads a local YAML configuration (your coordinates, time zone, and
display preferences), requests weather data from the provider you configure, and writes a
PNG. The planned LAN server publishes only that PNG. It does not send telemetry. Your
coordinates are sent only to the weather provider you select and are never written to the
repository; `config.yaml` is git-ignored.

The Kindle-side scripts run on a jailbroken device with root access. They are small on
purpose; review them before installing.

## Scope

In scope:

- Path traversal or unintended file writes through CLI output options.
- Unsafe parsing of the configuration file or of provider responses.
- Leakage of the configured location through logs or rendered output beyond what the
  selected skin intentionally displays.
- Anything in the Kindle-side scripts that could damage the device or expose it on the
  network beyond fetching the dashboard image.
- Dependency vulnerabilities with a plausible exploitation path in this tool.

Out of scope:

- Vulnerabilities in the Kindle firmware or in third-party jailbreak tooling; those belong
  to their respective projects.
- Findings from automated scanners with no demonstrated impact.

## Automated scanning

CI runs `bandit` over the package and `pip-audit` over the locked dependency set on every
pull request. Dependency updates are handled by Dependabot. The repository-level scanning
features that are enabled, with the date they were verified, are listed in
`docs/REPOSITORY_STATE.md`.
