# 🌤️ Paperwhite Weather

Turn a used Kindle Paperwhite into a quiet, always-on e-ink home display: time, current
weather, a multi-day forecast, and sun/twilight times, with interchangeable skins. A small
Python service renders the dashboard as a PNG; the jailbroken Kindle only downloads and
displays it.

[![CI](https://github.com/estcarisimo/paperwhite-weather/actions/workflows/ci.yml/badge.svg)](https://github.com/estcarisimo/paperwhite-weather/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Status: device bring-up (Sprint 1 done, 2026-09-19).** The renderer, data model, CLI,
> a first skin, and the LAN service work today with fixture data. The Kindle is jailbroken,
> reachable over SSH, and has displayed a live frame fetched from the service by DNS name.
> Unattended operation on the device (Sprint 3) and live weather (Sprint 2) are next; see
> [`docs/ROADMAP.md`](docs/ROADMAP.md).

## ✨ Features

- 🖼️ **Kindle-native rendering**: 1072x1448 grayscale PNG, quantized to the panel's 16 gray levels, landscape (default) or portrait, each with its own layout
- 🎨 **Skins on one data model**: layouts are independent of the weather source; `minimal` ships today, four more are planned
- 🔌 **Pluggable providers**: Open-Meteo for live data (no API key), a deterministic `mock` provider for development
- 🌅 **Civil twilight**: dawn, sunrise, sunset, and dusk computed locally from your coordinates
- 🕒 **Honest timestamps**: every frame shows when its data was fetched, so stale data is obvious
- 🧪 **Testable without a Kindle**: the renderer runs anywhere Python runs; CI uploads the rendered frame
- 📡 **LAN service**: `paperwhite serve` publishes `/dashboard/{landscape,portrait}.png` and a `/health` identity on port 8765; a failed fetch keeps the last good frame
- 🔒 **Your location stays local**: configuration is git-ignored and never leaves your network except to the weather provider you choose

## 🚀 Quick Start

```bash
git clone git@github.com:estcarisimo/paperwhite-weather.git
cd paperwhite-weather
uv sync
cp config.example.yaml config.yaml     # edit coordinates, time zone, units, skin
uv run paperwhite render --config config.yaml --output dashboard.png
```

Requirements: Python 3.10 or newer and [uv](https://github.com/astral-sh/uv). The
project is not on PyPI yet; install from GitHub as above.

## 📖 Usage

```bash
# Render one frame with fixture data (no network needed)
uv run paperwhite render --config config.example.yaml --output dashboard.png

# Render with live weather from Open-Meteo
uv run paperwhite render --config config.yaml --provider open-meteo --output dashboard.png

# Pin the clock for reproducible output; the value must carry a UTC offset
uv run paperwhite render -c config.example.yaml -o dashboard.png --now 2026-09-18T21:45:00+00:00

# Try a skin or the other orientation without editing the config
uv run paperwhite render -c config.example.yaml -o dashboard.png --skin minimal
uv run paperwhite render -c config.example.yaml -o dashboard.png --orientation portrait

# Serve frames on the LAN (fetches on a schedule, renders on request)
PAPERWHITE_PROVIDER=open-meteo uv run paperwhite serve --config config.yaml --port 8765
curl -s http://localhost:8765/health

# What is available
uv run paperwhite skins
uv run paperwhite providers
uv run paperwhite version
```

## 🔧 Configuration

The service reads `PAPERWHITE_CONFIG`, `PAPERWHITE_PROVIDER`, `PAPERWHITE_HOST`, and
`PAPERWHITE_PORT` from the environment (flags override them); `.env.example` documents them
and the systemd unit loads a git-ignored `.env`. The Kindle client will be told
the server's hostname at install time; nothing assumes a particular machine name.

`config.example.yaml` documents every option. Copy it to `config.yaml` (git-ignored):

```yaml
location:
  name: Chicago
  latitude: 41.8781
  longitude: -87.6298
  timezone: America/Chicago

units:
  temperature: fahrenheit  # celsius | fahrenheit
  wind: mph                # kmh | mph | ms

display:
  skin: minimal            # see `paperwhite skins`
  orientation: landscape   # landscape | portrait
  width: 1072              # Kindle Paperwhite 3 native framebuffer
  height: 1448
  time_format: 12h         # 12h | 24h
  refresh_minutes: 15
```

Unknown keys, invalid time zones, and out-of-range coordinates are rejected at load time.

## 🏗️ Architecture

Client-server, with the Kindle as a thin display. The reasoning, the alternatives, and the
open questions are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); device facts are in
[`docs/DEVICE.md`](docs/DEVICE.md).

```
src/paperwhite_weather/
├── config.py          # Location, Units, Display, Settings; load_settings(path)
├── models.py          # WeatherSnapshot and friends: the provider-independent data model
├── units.py           # temperature and speed conversions
├── fonts.py           # bundled DejaVu Sans (Bitstream Vera license)
├── sun.py             # civil dawn/dusk, sunrise/sunset via astral
├── providers/         # WeatherProvider protocol, mock and Open-Meteo providers, registry
├── skins/             # Skin protocol, format helpers, minimal skin, registry
├── render.py          # render_dashboard(): compose, rotate, quantize to 16 grays; render_offline()
├── service.py         # DashboardService (cache + per-minute frames) and the HTTP server
└── cli.py             # `paperwhite render | serve | skins | providers | version`
deploy/
├── systemd/           # user-level unit for the Raspberry Pi
└── avahi/             # optional mDNS advertisement
```

Deployment on the Pi is documented in [`docs/DEPLOY.md`](docs/DEPLOY.md).

## 🧪 Development

```bash
uv sync
uv run pre-commit install
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/paperwhite_weather
uv run pytest --cov=paperwhite_weather
```

Every change lands through a pull request with green CI and an independent review; see
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`.github/REVIEW.md`](.github/REVIEW.md).

## 📊 Example Output

```
$ uv run paperwhite render --config config.example.yaml --output dashboard.png --now 2026-09-18T21:45:00+00:00
INFO paperwhite_weather.render: Rendering skin 'minimal' on a 1448x1072 canvas
Rendered skin 'minimal' (landscape, 1072x1448) from 'mock' data fetched at 2026-09-18 21:45 UTC -> dashboard.png

$ uv run paperwhite skins
minimal

$ uv run paperwhite version
paperwhite-weather 0.1.0
```

The `minimal` skin rendered from the mock provider, scaled down. The landscape frame is
shown as it looks on the wall; the PNG the Kindle receives is rotated to the portrait
framebuffer.

<p align="center">
  <img src="docs/img/minimal-landscape-view.png" alt="Minimal skin, landscape" width="560">
</p>
<p align="center">
  <img src="docs/img/minimal-portrait.png" alt="Minimal skin, portrait" width="300">
</p>

## 🤝 Contributing

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) first, then:

1. Fork the repository
2. Create a branch (`git switch -c feat/my-skin`)
3. Commit your changes with a `CHANGELOG.md` entry
4. Push the branch
5. Open a pull request

## 📄 License

MIT; see [`LICENSE`](LICENSE). The bundled DejaVu Sans fonts are under the Bitstream Vera
license; see
[`src/paperwhite_weather/assets/fonts/LICENSE-DejaVu.txt`](src/paperwhite_weather/assets/fonts/LICENSE-DejaVu.txt).

## 🔗 Related Resources

Prior art studied for deployment, framebuffer, and refresh ideas. This project is an
original implementation and does not build on any of them.

- [pytatbro/weather-dashboard-kindle](https://github.com/pytatbro/weather-dashboard-kindle)
- [abbymartin/eink-dashboard](https://github.com/abbymartin/eink-dashboard)
- [jefftko/kindle-dashboard](https://github.com/jefftko/kindle-dashboard)
- [HimbeersaftLP/KindleDashboard](https://github.com/HimbeersaftLP/KindleDashboard)
- [Open-Meteo](https://open-meteo.com/), the weather provider (CC BY 4.0 data, free for non-commercial use)
- [astral](https://github.com/sffjunkie/astral), the sun-position library used for civil twilight
- [MobileRead Kindle Developer's Corner](https://www.mobileread.com/forums/forumdisplay.php?f=150), home of the jailbreak tooling

## 🙏 Acknowledgements

The project was prompted by [Ryan Peterman](https://x.com/ryanlpeterman)'s September 2026
post showing a jailbroken Kindle used as a Linux terminal: an old Kindle is a low-power,
high-contrast, Wi-Fi-connected e-ink computer waiting for a job.
