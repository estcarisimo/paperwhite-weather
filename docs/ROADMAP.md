# Roadmap

Sprint plan as of 2026-09-18. Sprints are scoped by outcome, not by calendar; a sprint
closes when its "done when" line is true and the work is on `main`. The Notion page
"Paperwhite Weather" holds the session log; this file mirrors the plan.

Milestone letters (M0–M4) refer to the Notion page.

## Sprint 0 — Foundation (this sprint)

Goal: a public repository a contributor can clone, run, and extend without a Kindle.

- [x] Repository, license, community files, review gate, CI, branch ruleset.
- [x] Configuration model and `config.example.yaml`.
- [x] `WeatherSnapshot` data model with aware timestamps.
- [x] `mock` provider and `minimal` skin; renderer with orientation and quantization.
- [x] `paperwhite render` CLI; tests with a coverage floor.
- [x] Architecture decision, device notes, this roadmap.
- [ ] Agree on the architecture (client-server) and this plan.

Done when: CI is green on `main`, the ruleset is active, and the decision in
`docs/ARCHITECTURE.md` is accepted.

## Sprint 1 — Device bring-up (M0)

Goal: shell access to the Kindle and a static image on its screen.

- [ ] Re-read the current WinterBreak thread; jailbreak the Paperwhite 3; install the
      hotfix, KUAL, MRPI, USBNetwork.
- [ ] Record `eips -i`, `uname -a`, tool availability, and package versions in
      `docs/DEVICE.md`; move the panel geometry from "assumed" to "verified".
- [ ] Copy a `paperwhite render` PNG to the device and display it with `eips -g`.
- [ ] Check readability of the `minimal` skin from across a room; adjust type sizes.
- [ ] Measure: Wi-Fi reconnect time, whether RTC wake from suspend works, idle battery
      drain over a night.

Done when: a frame rendered by this package is on the e-ink panel and `docs/DEVICE.md`
has no "assumed" entries left for the panel and the toolchain.

## Sprint 2 — Live weather service (M2)

Goal: real data, refreshed automatically, served on the LAN.

- [ ] `open-meteo` provider (current, daily low/high, precipitation probability,
      condition mapping from WMO weather codes, sunrise/sunset) with a recorded response
      fixture and tests.
- [ ] Civil dawn/dusk computed locally from coordinates (evaluate `astral`; otherwise
      implement the standard solar-position formulas with a `math`-marked test against a
      published table).
- [ ] `paperwhite serve`: refresh every `refresh_minutes`, keep the last good snapshot,
      serve `/dashboard.png` and `/health` on the LAN; systemd unit for the Raspberry Pi.
- [ ] Offline frame when no snapshot has ever succeeded; "Updated" footer already covers
      stale data.

Done when: the Pi serves a live frame that updates on schedule and survives an API outage.

## Sprint 3 — Kindle client (M2, deployment)

Goal: the dashboard runs unattended on the wall.

- [ ] `kindle/paperwhite.sh`: fetch, display, periodic full clear against ghosting, RTC
      wake and suspend, Wi-Fi handling, fallback to the cached image.
- [ ] KUAL extension to start/stop it; install instructions verified on the device.
- [ ] Battery measurement over a week at 15-minute refresh; decide on the clock question.
- [ ] Photos of the device for the README.

Done when: the Kindle has shown live weather for seven days without manual intervention.

## Sprint 4 — Skins and icons (M3)

Goal: the five skins from the concept, selectable by configuration.

- [ ] Monochrome condition icon set (own drawings or a permissively licensed set, with the
      license file next to it).
- [ ] `newspaper`, `weather-station`, `big-clock`, `forecast` skins.
- [ ] Golden-image tests per skin with provenance; CI uploads every skin as an artifact.
- [ ] Optional data in the model: feels-like, humidity, wind, UV, moon phase.

Done when: every skin renders both orientations from the mock provider and is pictured in
the README.

## Sprint 5 — Open-source polish and 0.1.0 (M4)

Goal: someone else can do this with their Kindle in an evening.

- [ ] README with photos, one-command Pi setup, documented Kindle setup.
- [ ] `CITATION.cff` validated, `SECURITY.md` links verified, private vulnerability
      reporting confirmed (see `docs/REPOSITORY_STATE.md`).
- [ ] Release 0.1.0 on GitHub; PyPI only after the name is confirmed and Trusted
      Publishing is configured.

## Parking lot

- Additional Kindle models (different framebuffer sizes; `display.width/height` already
  configurable).
- Severe-weather alerts, air quality, golden/blue hour.
- Static-hosting deployment variant (render in a scheduled job, fetch from a public URL).
