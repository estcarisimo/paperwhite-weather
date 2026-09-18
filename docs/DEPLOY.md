# Deploying the service on the Raspberry Pi

Verified on `smokingpi` (Raspberry Pi 5, Raspberry Pi OS, user `smokingpi`) on 2026-09-18.
Every command below was run there before it was written down.

## What runs

`paperwhite serve` fetches weather every `display.refresh_minutes`, keeps the last good
snapshot, and answers on port 8765:

| Path | Response |
| --- | --- |
| `/health` | JSON: `service`, `version`, `status` (`ok` or `no-data`), provider, skin, default orientation, refresh interval, `fetched_at`, `last_attempt_at`, `last_error`, counters |
| `/dashboard.png` | Frame in the configured default orientation |
| `/dashboard/landscape.png`, `/dashboard/portrait.png` | Frame in that orientation |
| `/` | Plain-text list of the routes |

Frames are rendered when requested, with the request time on the clock, and memoized per
minute. Until the first successful fetch the frames say "No weather data yet" with the time
of the last fetch attempt (or "No fetch attempted yet"), not the request time, so a long
outage looks like one. A failed refresh keeps the previous snapshot and is reported in
`/health` as `last_error`.

## Install

```bash
cd ~/paperwhite-weather
uv sync
cp config.example.yaml config.yaml         # then edit coordinates, time zone, units
mkdir -p ~/.config/systemd/user
sed "s|%REPO%|$PWD|g" deploy/systemd/paperwhite-weather.service \
    > ~/.config/systemd/user/paperwhite-weather.service
systemctl --user daemon-reload
systemctl --user enable --now paperwhite-weather.service
```

Requirements: `loginctl show-user $USER -p Linger` must print `Linger=yes` so the user
service starts at boot without a login (`sudo loginctl enable-linger $USER` otherwise).
Port 8765 must be free (`ss -ltn | grep 8765`).

## Check

```bash
systemctl --user status paperwhite-weather.service
journalctl --user -u paperwhite-weather.service -f
curl -s http://smokingpi.lan:8765/health | python3 -m json.tool
curl -s -o /tmp/dashboard.png http://smokingpi.lan:8765/dashboard.png
```

On 2026-09-18 the service answered on `http://smokingpi.lan:8765/` from the Pi itself
(`getent hosts smokingpi.lan` → `192.168.86.27`, resolved by the router). Checking the
same URL from the Kindle is a Sprint 1 task.

The unit runs the mock provider until a live provider exists; change `--provider` in the
installed unit (or in `deploy/systemd/paperwhite-weather.service` and reinstall) when it
does.

## Optional: mDNS advertisement

```bash
sudo cp deploy/avahi/paperwhite-weather.service /etc/avahi/services/
```

Installed on `smokingpi` on 2026-09-18. **Unverified**: `avahi-utils` is not installed
there, so `avahi-browse -rt _paperwhite-weather._tcp` could not be run. The Kindle client
does not depend on it.

## Update

```bash
cd ~/paperwhite-weather && git pull && uv sync
systemctl --user restart paperwhite-weather.service
```

## Remove

```bash
systemctl --user disable --now paperwhite-weather.service
rm ~/.config/systemd/user/paperwhite-weather.service
sudo rm /etc/avahi/services/paperwhite-weather.service   # if installed
```
