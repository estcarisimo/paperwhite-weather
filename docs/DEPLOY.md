# Deploying the service on the Raspberry Pi

Verified on the maintainer's Raspberry Pi 5 (Raspberry Pi OS; hostname `smokingpi`, used
below only where an actual result is quoted) on 2026-09-18. Every command below was run
there before it was written down. Replace `<server>` with your machine's hostname.

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

## Configuration

The unit passes settings as environment variables, so it never needs editing:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PAPERWHITE_CONFIG` | `<repo>/config.yaml` | Configuration file (git-ignored) |
| `PAPERWHITE_PROVIDER` | `mock` | Weather provider name (`paperwhite providers`) |
| `PAPERWHITE_HOST` | `0.0.0.0` | Interface to listen on |
| `PAPERWHITE_PORT` | `8765` | TCP port |

Override any of them in `<repo>/.env` (git-ignored; `cp .env.example .env` and edit) or
with `systemctl --user edit paperwhite-weather.service`. The same variables work for a
manual `paperwhite serve`; note that the shell does not read `.env` by itself, only the
unit does (`EnvironmentFile`).

## Install

One command, from the checkout:

```bash
deploy/install.sh
```

It runs `uv sync --locked`, creates `config.yaml` and `.env` from the examples if they
do not exist (never overwriting them), writes the unit with the checkout's path, enables
and restarts it, warns if lingering is off, and waits for `/health` to answer. Re-run it
after editing `.env` or after `git pull`. Verified on the maintainer's Pi on 2026-09-20,
both on a fresh clone (mock provider, `status ok`, 1.4 s) and over the existing install
(config and `.env` kept, `open-meteo`, `status ok`).

Then edit `config.yaml` (coordinates, time zone, units, skin) and `.env`
(`PAPERWHITE_PROVIDER=open-meteo` for live weather), and
`systemctl --user restart paperwhite-weather.service`.

The same steps by hand:

```bash
cd ~/paperwhite-weather
uv sync
cp config.example.yaml config.yaml         # then edit coordinates, time zone, units
cp .env.example .env                       # optional: provider, host, port
mkdir -p ~/.config/systemd/user
sed "s|%REPO%|$PWD|g" deploy/systemd/paperwhite-weather.service \
    > ~/.config/systemd/user/paperwhite-weather.service
systemctl --user daemon-reload
systemctl --user enable --now paperwhite-weather.service
```

Requirements: `uv` on the path; `loginctl show-user $USER -p Linger` must print
`Linger=yes` so the user service starts at boot without a login
(`sudo loginctl enable-linger $USER` otherwise); port 8765 must be free
(`ss -ltn | grep 8765`), or set `PAPERWHITE_PORT` in `.env`.

## Check

```bash
systemctl --user status paperwhite-weather.service
journalctl --user -u paperwhite-weather.service -f
curl -s http://<server>.lan:8765/health | python3 -m json.tool
curl -s -o /tmp/dashboard.png http://<server>.lan:8765/dashboard.png
```

On 2026-09-18 the service answered on `http://smokingpi.lan:8765/` from the Pi itself
(`getent hosts smokingpi.lan` → `192.168.86.27`, resolved by the router). Whether your
router resolves `<hostname>.lan` is router-specific; `/health` reports the server's
`hostname`, and the Kindle client falls back to a subnet scan (see `docs/ARCHITECTURE.md`).
Verified from the Kindle on 2026-09-19: `wget` of `/health` and `/dashboard.png` by that
name worked on the device (`docs/DEVICE.md`).

The unit defaults to the mock provider; put `PAPERWHITE_PROVIDER=open-meteo` in `.env`
for live weather (the maintainer's Pi runs it since the merge of PR #7, 2026-09-19).

## Optional: mDNS advertisement

```bash
sudo cp deploy/avahi/paperwhite-weather.service /etc/avahi/services/
```

Installed on the maintainer's Pi on 2026-09-18. **Unverified**: `avahi-utils` is not installed
there, so `avahi-browse -rt _paperwhite-weather._tcp` could not be run. The Kindle client
does not depend on it.

## Update

```bash
cd ~/paperwhite-weather && git pull && deploy/install.sh
```

(or `uv sync` and `systemctl --user restart paperwhite-weather.service` by hand).

## Remove

```bash
systemctl --user disable --now paperwhite-weather.service
rm ~/.config/systemd/user/paperwhite-weather.service
sudo rm /etc/avahi/services/paperwhite-weather.service   # if installed
```
