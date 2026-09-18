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
- [x] Architecture (client-server, Pi as server) and this plan accepted by the maintainer
      (2026-09-18). Decisions: landscape default, both orientations served, tap to switch,
      DNS-name discovery, skins last.
- [x] Real landscape layout for `minimal`; `--orientation` on the CLI.

Done: CI green on `main`, ruleset active, decision accepted.

## Sprint 1 — Device bring-up (M0)

Goal: shell access to the Kindle and a static image on its screen.

- [ ] Jailbreak the Paperwhite 3 with WinterBreak2 (runbook in `docs/DEVICE.md`:
      fill the disk against OTA, stage `winterbreak2/`, browser step on the device);
      install KUAL, MRPI, USBNetwork.
- [ ] Record `eips -i`, `uname -a`, tool availability, input device nodes, and package
      versions in `docs/DEVICE.md`; move the panel geometry from "assumed" to "verified".
- [ ] Copy a `paperwhite render` PNG to the device and display it with `eips -g`, in both
      orientations; confirm the landscape rotation direction.
- [ ] From the device: `wget -O /dev/null http://smokingpi.lan:8765/health` to confirm
      DNS-name discovery works from the Kindle's resolver.
- [ ] Probe touch: which `/dev/input/event*` node fires on a tap, and whether it fires
      with the stock GUI running.
- [ ] Check readability of the `minimal` skin from across a room; adjust type sizes.
- [ ] Measure: Wi-Fi reconnect time, whether RTC wake from suspend works, idle battery
      drain over a night.

Done when: a frame rendered by this package is on the e-ink panel in landscape and
`docs/DEVICE.md` has no "assumed" entries left for the panel, the toolchain, and touch.

## Sprint 2 — Live weather service (M2)

Goal: real data, refreshed automatically, served on the LAN.

- [ ] `open-meteo` provider (current, daily low/high, precipitation probability,
      condition mapping from WMO weather codes, sunrise/sunset) with a recorded response
      fixture and tests.
- [ ] Civil dawn/dusk computed locally from coordinates (evaluate `astral`; otherwise
      implement the standard solar-position formulas with a `math`-marked test against a
      published table).
- [x] `paperwhite serve`: refresh every `refresh_minutes`, render both orientations, keep
      the last good snapshot, serve `/dashboard/{landscape,portrait}.png`, `/dashboard.png`
      and the `/health` identity on port 8765; systemd unit and Avahi service file for the
      Raspberry Pi (installed on `smokingpi` 2026-09-18 with the mock provider).
- [ ] Switch the installed unit to the live provider once it exists.
- [x] Offline frame when no snapshot has ever succeeded; "Updated" footer already covers
      stale data.

Done when: the Pi serves a live frame that updates on schedule and survives an API outage.

## Sprint 3 — Kindle client (M2, deployment)

Goal: the dashboard runs unattended on the wall.

- [ ] `kindle/paperwhite.sh`: discover the server (config → `.lan` → `.local` → scan),
      fetch the image for the current orientation, display, periodic full clear against
      ghosting, RTC wake and suspend, Wi-Fi handling, fallback to the cached image.
- [ ] Tap to toggle orientation, persisted on the device.
- [ ] KUAL extension to start/stop it; install instructions verified on the device.
- [ ] Battery measurement over a week at 15-minute refresh; decide on the clock question.
- [ ] Photos of the device for the README.

Done when: the Kindle has shown live weather for seven days without manual intervention.

## Sprint 4 — Skins and icons (M3)

Goal: the five skins from the concept, selectable by configuration. This is where most of
the refinement time goes, once the device runs unattended.

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
