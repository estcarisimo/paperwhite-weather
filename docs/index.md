# Paperwhite Weather

Turn a used Kindle Paperwhite into a quiet, always-on e-ink home display: time, current
weather, a multi-day forecast, and sun/twilight times, with interchangeable skins. A small
Python service renders the dashboard as a PNG; the jailbroken Kindle only downloads and
displays it.

The source, the issue tracker, and the releases are on
[GitHub](https://github.com/estcarisimo/paperwhite-weather). The project is installed from
there; it is not published to PyPI or any other package index.

## How it works

Client-server, with the Kindle as a thin display. A machine on your LAN that stays on (a
Raspberry Pi will do) runs `paperwhite serve`: it fetches Open-Meteo every 15 minutes,
keeps the last good snapshot, and renders a 1072x1448 PNG on request, quantized to the
panel's 16 grays. The Kindle runs a small POSIX shell script that finds the server by name,
fetches the frame, paints it with `eips`, and suspends until the next refresh with an RTC
wake. [Architecture](ARCHITECTURE.md) records the decision and its alternatives.

## Put it on the wall

1. **The server.** From the checkout on the always-on machine, `deploy/install.sh`
   installs a user-level systemd unit and checks `/health`; re-running it after
   `git pull` is the update. [Deploying the service](DEPLOY.md) has the details.
2. **The Kindle.** Jailbreak it first: [Device notes](DEVICE.md) has the runbook that was
   followed for a Paperwhite 3 on firmware 5.16.2.1.1, with the legal note. Then copy the
   client to the device and tell it your server's hostname:
   [kindle/README.md](https://github.com/estcarisimo/paperwhite-weather/blob/main/kindle/README.md).

## The skins

Seven skins on one data model, from quiet to detailed, each with a landscape and a
portrait layout. Rendered from the mock provider at the same instant; landscape as it
reads on the wall.

| Skin | Landscape | Portrait |
| --- | --- | --- |
| `minimal` (default) | ![minimal, landscape](img/minimal-landscape-view.png){ width="420" } | ![minimal, portrait](img/minimal-portrait.png){ width="200" } |
| `big-clock` | ![big-clock, landscape](img/big-clock-landscape-view.png){ width="420" } | ![big-clock, portrait](img/big-clock-portrait.png){ width="200" } |
| `forecast` | ![forecast, landscape](img/forecast-landscape-view.png){ width="420" } | ![forecast, portrait](img/forecast-portrait.png){ width="200" } |
| `graphic` | ![graphic, landscape](img/graphic-landscape-view.png){ width="420" } | ![graphic, portrait](img/graphic-portrait.png){ width="200" } |
| `timeline` | ![timeline, landscape](img/timeline-landscape-view.png){ width="420" } | ![timeline, portrait](img/timeline-portrait.png){ width="200" } |
| `weather-station` | ![weather-station, landscape](img/weather-station-landscape-view.png){ width="420" } | ![weather-station, portrait](img/weather-station-portrait.png){ width="200" } |
| `newspaper` | ![newspaper, landscape](img/newspaper-landscape-view.png){ width="420" } | ![newspaper, portrait](img/newspaper-portrait.png){ width="200" } |

## Pages

- [Architecture](ARCHITECTURE.md): the client-server decision, alternatives, open questions.
- [Deploying the service](DEPLOY.md): the Raspberry Pi unit, its routes, configuration, checks.
- [Device notes](DEVICE.md): what was verified on the Kindle, the jailbreak runbook, power measurements.
- [Roadmap](ROADMAP.md): sprints, what is done, what is open.
- [Repository state](REPOSITORY_STATE.md): branch protection, security features, CI, verified with dates.
