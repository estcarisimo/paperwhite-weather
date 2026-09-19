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

- [x] Jailbreak the Paperwhite 3 with WinterBreak2 (2026-09-18); install KUAL, MRPI,
      USBNetwork; SSH over Wi-Fi with a key (2026-09-19).
- [x] Record `eips -i`, `uname -a`, tool availability, input device nodes, and package
      versions in `docs/DEVICE.md`; panel geometry verified (1072x1448, 8-bit gray).
- [x] Fetch a live frame from the Pi on the device and display it with `eips -g`
      (2026-09-19, landscape).
- [ ] Display the portrait frame too; confirm the landscape rotation direction as mounted.
- [x] From the device: `wget http://smokingpi.lan:8765/health` returned the service
      identity, so DNS-name discovery works from the Kindle's resolver (2026-09-19).
- [x] Touch: `/dev/input/event1` (`cyttsp4_mt`) fires on a tap with the stock GUI running.
- [x] First look at the `minimal` skin on the panel (2026-09-19): readable; the stock GUI
      repainted over it on a tap, so a longer readability check waits for Sprint 3.
- [ ] Measure: Wi-Fi reconnect time, whether RTC wake from suspend works, idle battery
      drain over a night. (Moved to Sprint 3, where the client script exercises them.)

Done: a frame rendered by this package is on the e-ink panel in landscape and
`docs/DEVICE.md` has no "assumed" entries left for the panel, the toolchain, and touch.
Open items above are listed again under Sprint 3.

## Sprint 2 — Live weather service (M2)

Goal: real data, refreshed automatically, served on the LAN.

- [x] `open-meteo` provider (current, daily low/high, precipitation probability,
      condition mapping from WMO weather codes) with a recorded response fixture and
      tests (2026-09-19).
- [x] Civil dawn/dusk computed locally from coordinates with `astral`; `math`-marked test
      against the US Naval Observatory table for the fixture date (2026-09-19).
- [x] `paperwhite serve`: refresh every `refresh_minutes`, render both orientations, keep
      the last good snapshot, serve `/dashboard/{landscape,portrait}.png`, `/dashboard.png`
      and the `/health` identity on port 8765; systemd unit and Avahi service file for the
      Raspberry Pi (installed on the maintainer's Pi 2026-09-18 with the mock provider).
- [x] Installed unit on the maintainer's Pi switched to `open-meteo` via `.env` (2026-09-19).
- [x] Offline frame when no snapshot has ever succeeded; "Updated" footer already covers
      stale data.

Done when: the Pi serves a live frame that updates on schedule and survives an API outage.

## Sprint 3 — Kindle client (M2, deployment)

Goal: the dashboard runs unattended on the wall.

- [ ] `kindle/paperwhite.sh`: discover the server (config → `.lan` → `.local` → scan),
      fetch the image for the current orientation, display, periodic full clear against
      ghosting, RTC wake and suspend, Wi-Fi handling, fallback to the cached image.
- [ ] Tap to toggle orientation, persisted on the device.
- [ ] Keep our frame on screen: stop the stock GUI or repaint over it; suppress the
      screensaver (`preventScreenSaver`).
- [ ] Portrait frame on the panel; confirm the landscape rotation direction as mounted.
- [ ] Measure Wi-Fi reconnect time, RTC wake from suspend (`/sys/class/rtc/rtc0/wakealarm`),
      and idle battery drain over a night, before the week-long run.
- [ ] Readability of the `minimal` skin from across a room, once the frame stays up;
      adjust type sizes.
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
