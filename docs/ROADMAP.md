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
- [x] Installed unit on the maintainer's Pi switched to `open-meteo` via `.env` after the
      merge of PR #7 (2026-09-19).
- [x] Offline frame when no snapshot has ever succeeded; "Updated" footer already covers
      stale data.

Done when: the Pi serves a live frame that updates on schedule and survives an API outage.

## Sprint 3 — Kindle client (M2, deployment)

Goal: the dashboard runs unattended on the wall.

- [x] `kindle/paperwhite.sh`: discover the server (config → last known → `.lan` →
      `.local` → bare → scan), fetch the image for the current orientation, display,
      periodic full clear against ghosting, fallback to the cached image (2026-09-19).
- [x] RTC wake and suspend between refreshes (2026-09-19; awake measured 1.3 %/h, so
      suspend is the default with a 90 s tap window).
- [x] Tap to toggle orientation, persisted on the device (2026-09-19, synthetic taps).
- [x] Keep our frame on screen: `stop framework`; `preventScreenSaver 1`; frontlight off
      and restored on stop (2026-09-19).
- [ ] Portrait frame on the panel; confirm the landscape rotation direction as mounted.
- [x] Measure Wi-Fi reconnect time (connected on resume), RTC wake from suspend (to the
      second), and idle battery drain over a night (1.3 %/h awake) (2026-09-19).
- [ ] Battery drain with suspend, over a night (measuring from 2026-09-19 15:49 UTC).
- [ ] Readability of the `minimal` skin from across a room, once the frame stays up;
      adjust type sizes.
- [x] KUAL extension (Start, Stop, Show one frame, Toggle, Status) installed; `install.sh`
      over USB still a draft (installed over SSH instead).
- [x] Start at boot: `enable-boot` writes an upstart job; verified with a reboot
      (2026-09-19).
- [ ] Battery measurement over a week at 15-minute refresh; decide on the clock question.
- [ ] Photos of the device for the README.

Done when: the Kindle has shown live weather for seven days without manual intervention.

## Sprint 4 — Skins and icons (M3)

Goal: the five skins from the concept, selectable by configuration. This is where most of
the refinement time goes, once the device runs unattended.

- [x] Monochrome condition icon set, drawn with Pillow primitives (`icons.py`), no
      external assets (2026-09-19).
- [x] `newspaper`, `weather-station`, `big-clock`, `forecast` skins, portrait and landscape
      (2026-09-19, first versions; refinement continues).
- [x] Golden-image tests per skin with provenance (`tests/goldens/README.md`); CI uploads
      the `skins-gallery` artifact (2026-09-19).
- [x] Optional data shown where present: feels-like, humidity, wind, precipitation
      (weather-station grid, newspaper deck). UV and moon phase: not in the model yet.
- [ ] Refine layouts on the physical panel: type sizes from across the room, ghosting
      after partial refreshes, the amount of empty space in portrait.
- [ ] UV index and moon phase in the model and the weather-station skin.

### Refinement backlog (maintainer review of the first versions, 2026-09-19)

The first versions read well; the direction is **fewer words, more pictures**.

- [ ] **Sun times as a graphic**, not four labeled clocks: a horizon arc from civil dawn
      to civil dusk with the sun's current position, sunrise and sunset marked, twilight
      as gray bands. One icon-like element replaces "Dawn 6:12 AM  Sunrise 6:40 AM ...".
- [ ] **Temperature range as a scale**: today's low/high (and the forecast days') drawn
      as horizontal bars on a shared axis, with the current temperature marked, rather
      than "H 75°  L 57°" text. Aligned bars make the week comparable at a glance.
- [ ] **Less text where a symbol carries the meaning**: precipitation probability as a
      drop icon with the number, wind as an arrow with the speed, humidity as a
      half-filled drop. The `newspaper` skin stays deliberately textual; the other four
      move toward icons.
- [ ] **Icon refinement**: the condition icons are a first cut; review each at panel
      scale (photo of the device), unify stroke weights, and consider distinct glyphs
      for showers versus steady rain and for night (clear night, partly cloudy night)
      once the model knows whether it is night.
- [ ] Portrait layouts leave empty space at the bottom (`newspaper`, `weather-station`);
      either grow the forecast or add the sun graphic there.

Done: every skin renders both orientations from the mock provider and is pictured in the
README. Refinement items above stay open and are where the project spends its time next.

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
