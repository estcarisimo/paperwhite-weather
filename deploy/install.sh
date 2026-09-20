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
host="$(sed -n 's/^PAPERWHITE_HOST=//p' "$repo/.env" 2>/dev/null | tail -n 1)"
host="${host:-0.0.0.0}"
# The health probe goes to loopback when the service listens on every interface.
[ "$host" = "0.0.0.0" ] && host="127.0.0.1"

for tool in uv systemctl curl; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "$tool is not installed; this script needs uv, systemctl, and curl" >&2
        exit 1
    }
done

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

echo "==> waiting for /health on $host:$port"
i=0
until curl -sf "http://$host:$port/health" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "the service did not answer within 30 s; see: journalctl --user -u $unit -e" >&2
        exit 1
    fi
    sleep 1
done
curl -s "http://$host:$port/health"
echo
echo "==> done. Tell the Kindle client SERVER_HOST=$(hostname) (and SERVER_PORT=$port if you"
echo "    changed it); it tries $(hostname).lan, .local, and the bare name, then scans the"
echo "    subnet (see kindle/README.md)."
