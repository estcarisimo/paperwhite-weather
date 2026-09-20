#!/bin/sh
# One-command setup of the dashboard service as a user-level systemd unit.
# Usage, from the checkout on the machine that will serve the Kindle:
#
#   deploy/install.sh
#
# Idempotent: re-running it updates the environment and the unit and restarts the
# service, and never overwrites an existing config.yaml or .env. What it does is the
# "Install" section of docs/DEPLOY.md, step by step.
set -eu

repo="$(cd "$(dirname "$0")/.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit="paperwhite-weather.service"
port="$(sed -n 's/^PAPERWHITE_PORT=//p' "$repo/.env" 2>/dev/null | tail -n 1)"
port="${port:-8765}"

command -v uv >/dev/null 2>&1 || {
    echo "uv is not installed; see https://github.com/astral-sh/uv" >&2
    exit 1
}
command -v systemctl >/dev/null 2>&1 || {
    echo "systemctl not found; this script installs a systemd user unit" >&2
    exit 1
}

cd "$repo"
echo "==> uv sync"
uv sync --locked

if [ -f config.yaml ]; then
    echo "==> kept existing config.yaml"
else
    cp config.example.yaml config.yaml
    echo "==> wrote config.yaml from config.example.yaml; edit the location, units, and skin"
fi
if [ -f .env ]; then
    echo "==> kept existing .env"
else
    cp .env.example .env
    echo "==> wrote .env from .env.example (mock provider; set PAPERWHITE_PROVIDER=open-meteo for live weather)"
fi

echo "==> installing $unit_dir/$unit"
mkdir -p "$unit_dir"
sed "s|%REPO%|$repo|g" deploy/systemd/$unit > "$unit_dir/$unit"
systemctl --user daemon-reload
systemctl --user enable "$unit" >/dev/null 2>&1
systemctl --user restart "$unit"

if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
    echo "==> lingering is off: the service will not start at boot without a login."
    echo "    Run: sudo loginctl enable-linger $USER"
fi

echo "==> waiting for /health on port $port"
i=0
until curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "the service did not answer within 30 s; see: journalctl --user -u $unit -e" >&2
        exit 1
    fi
    sleep 1
done
curl -s "http://127.0.0.1:$port/health"
echo
echo "==> done. The Kindle reaches this machine as http://$(hostname).lan:$port/ (see kindle/README.md)."
