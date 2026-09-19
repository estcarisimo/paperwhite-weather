#!/bin/sh
# Paperwhite Weather: Kindle client.
# Runs as root on a jailbroken Kindle (BusyBox ash). Fetches the dashboard frame from the
# server, paints it with eips, toggles orientation on a tap, repeats.
#
# Verified on a Kindle Paperwhite 3, firmware 5.16.2.1.1, on 2026-09-19 (docs/DEVICE.md).
#
# Files (all under /mnt/us/paperwhite):
#   config              KEY=value lines; see config.example
#   state/orientation   "landscape" or "portrait"; toggled by a tap
#   state/server_url    last server that answered /health (discovery cache)
#   cache/current.png   last frame fetched; shown when the server is unreachable
#   paperwhite.log      one line per event
#
# Usage: paperwhite.sh start|stop|once|status|toggle   (loop: internal, used by start)

BASE="/mnt/us/paperwhite"
CONFIG="$BASE/config"
STATE="$BASE/state"
CACHE="$BASE/cache"
LOG="$BASE/paperwhite.log"
PIDFILE="$STATE/paperwhite.pid"
EIPS="/usr/sbin/eips"
TOUCH_DEVICE="/dev/input/event1"

# Defaults; the config file overrides them.
SERVER_HOST=""
SERVER_PORT="8765"
SERVER_URL=""
REFRESH_MINUTES="15"
FULL_REFRESH_EVERY="4"
TAP_WINDOW_SECONDS="60"
STOP_FRAMEWORK="yes"
FRONTLIGHT="0"
LOG_LINES="500"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
    if [ "$(wc -l < "$LOG")" -gt "$LOG_LINES" ]; then
        tail -n "$LOG_LINES" "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    fi
}

load_config() {
    mkdir -p "$STATE" "$CACHE"
    # shellcheck disable=SC1090
    [ -f "$CONFIG" ] && . "$CONFIG"
    [ -n "$PAPERWHITE_SERVER" ] && SERVER_HOST="$PAPERWHITE_SERVER"
    ORIENTATION="$(cat "$STATE/orientation" 2>/dev/null)"
    case "$ORIENTATION" in
        landscape|portrait) ;;
        *) ORIENTATION="landscape"; printf '%s\n' "$ORIENTATION" > "$STATE/orientation" ;;
    esac
}

# --- discovery -----------------------------------------------------------------------

health_ok() {
    # $1: base URL. True if /health answers with our service identity.
    wget -q -T 4 -O - "$1/health" 2>/dev/null | grep -q '"service": *"paperwhite-weather"'
}

candidates() {
    [ -n "$SERVER_URL" ] && printf '%s\n' "$SERVER_URL"
    cat "$STATE/server_url" 2>/dev/null
    if [ -n "$SERVER_HOST" ]; then
        printf 'http://%s.lan:%s\n' "$SERVER_HOST" "$SERVER_PORT"
        printf 'http://%s.local:%s\n' "$SERVER_HOST" "$SERVER_PORT"
        printf 'http://%s:%s\n' "$SERVER_HOST" "$SERVER_PORT"
    fi
}

scan_subnet() {
    # Try every host on the default gateway's /24 for /health, 32 at a time.
    gateway="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
    [ -n "$gateway" ] || return 1
    prefix="${gateway%.*}"
    i=1
    while [ "$i" -le 254 ]; do
        j=0
        while [ "$j" -lt 32 ] && [ "$i" -le 254 ]; do
            url="http://$prefix.$i:$SERVER_PORT"
            ( health_ok "$url" && printf '%s\n' "$url" > "$STATE/scan_hit" ) &
            i=$((i + 1)); j=$((j + 1))
        done
        wait
        if [ -s "$STATE/scan_hit" ]; then
            cat "$STATE/scan_hit"; rm -f "$STATE/scan_hit"; return 0
        fi
    done
    return 1
}

discover() {
    for url in $(candidates | awk '!seen[$0]++'); do
        if health_ok "$url"; then
            printf '%s\n' "$url" > "$STATE/server_url"
            printf '%s\n' "$url"
            return 0
        fi
    done
    log "discovery: no configured server answered; scanning the subnet"
    url="$(scan_subnet)" || return 1
    printf '%s\n' "$url" > "$STATE/server_url"
    printf '%s\n' "$url"
}

# --- display -------------------------------------------------------------------------

fetch_frame() {
    # Downloads the frame for the current orientation into the cache. Returns 1 on failure.
    server="$(discover)" || { log "fetch: no server found"; return 1; }
    if wget -q -T 15 -O "$CACHE/next.png" "$server/dashboard/$ORIENTATION.png" 2>/dev/null \
        && [ -s "$CACHE/next.png" ]; then
        mv "$CACHE/next.png" "$CACHE/current.png"
        return 0
    fi
    rm -f "$CACHE/next.png"
    log "fetch: $server/dashboard/$ORIENTATION.png failed"
    return 1
}

paint() {
    # $1: "full" to clear first (fights ghosting), anything else for a partial update.
    [ -s "$CACHE/current.png" ] || { log "paint: no frame to show"; return 1; }
    [ "$1" = "full" ] && "$EIPS" -c > /dev/null 2>&1
    "$EIPS" -g "$CACHE/current.png" > /dev/null 2>&1
}

wait_for_tap() {
    # Blocks up to $1 seconds; returns 0 if the screen was touched.
    [ -e "$TOUCH_DEVICE" ] || { sleep "$1"; return 1; }
    timeout "$1" dd if="$TOUCH_DEVICE" bs=16 count=1 > /dev/null 2>&1
}

drain_touch() {
    # Swallow the rest of the gesture so one tap does not count twice.
    timeout 1 dd if="$TOUCH_DEVICE" bs=16 count=64 > /dev/null 2>&1
    return 0
}

toggle_orientation() {
    if [ "$ORIENTATION" = "landscape" ]; then ORIENTATION="portrait"; else ORIENTATION="landscape"; fi
    printf '%s\n' "$ORIENTATION" > "$STATE/orientation"
    log "orientation: $ORIENTATION"
}

# --- device power and GUI ------------------------------------------------------------

take_screen() {
    lipc-set-prop com.lab126.powerd preventScreenSaver 1 > /dev/null 2>&1
    # Remember the reader's frontlight level and set ours (an e-ink wall display wants none).
    lipc-get-prop com.lab126.powerd flIntensity > "$STATE/frontlight_saved" 2>/dev/null
    lipc-set-prop com.lab126.powerd flIntensity "$FRONTLIGHT" > /dev/null 2>&1
    if [ "$STOP_FRAMEWORK" = "yes" ]; then
        stop framework > /dev/null 2>&1 || true
        log "framework stopped"
    fi
}

release_screen() {
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 > /dev/null 2>&1
    saved="$(cat "$STATE/frontlight_saved" 2>/dev/null)"
    [ -n "$saved" ] && lipc-set-prop com.lab126.powerd flIntensity "$saved" > /dev/null 2>&1
    if [ "$STOP_FRAMEWORK" = "yes" ]; then
        start framework > /dev/null 2>&1 || true
        log "framework started"
    fi
}

# --- main loop -----------------------------------------------------------------------

run_loop() {
    trap 'exit 0' INT TERM
    take_screen
    cycle=0
    while :; do
        fetch_frame
        if [ $((cycle % FULL_REFRESH_EVERY)) -eq 0 ]; then paint full; else paint partial; fi
        cycle=$((cycle + 1))
        # Sleep until the next refresh, but wake on a tap to switch orientation.
        deadline=$(( $(date +%s) + REFRESH_MINUTES * 60 ))
        while :; do
            remaining=$(( deadline - $(date +%s) ))
            [ "$remaining" -gt 0 ] || break
            window="$TAP_WINDOW_SECONDS"
            [ "$remaining" -lt "$window" ] && window="$remaining"
            if wait_for_tap "$window"; then
                drain_touch
                toggle_orientation
                fetch_frame
                paint full
                cycle=0
            fi
        done
    done
}

running_pid() {
    pid="$(cat "$PIDFILE" 2>/dev/null)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && printf '%s\n' "$pid"
}

case "$1" in
    start)
        load_config
        if running_pid > /dev/null; then echo "already running (pid $(running_pid))"; exit 0; fi
        log "starting (server=${SERVER_URL:-${SERVER_HOST:-scan}}, orientation=$ORIENTATION)"
        # A new session so the loop outlives the SSH or KUAL shell that started it.
        setsid "$0" loop > /dev/null 2>&1 < /dev/null &
        sleep 1
        echo "started (pid $(running_pid || echo '?'))"
        ;;
    loop)
        load_config
        printf '%s\n' "$$" > "$PIDFILE"
        run_loop
        ;;
    stop)
        load_config
        if pid="$(running_pid)"; then
            # The loop is a session leader (setsid), so the negative PID takes its children
            # (the blocking touch read) with it. The restore is done here, not in the loop's
            # trap, because a trap cannot run while the shell waits on that read.
            kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
            rm -f "$PIDFILE"
            echo "stopped (pid $pid)"
        else
            echo "not running"
        fi
        release_screen
        log "stopped"
        ;;
    once)
        load_config
        fetch_frame; paint full
        ;;
    status)
        load_config
        if pid="$(running_pid)"; then echo "running (pid $pid)"; else echo "not running"; fi
        echo "orientation: $ORIENTATION"
        echo "server: $(cat "$STATE/server_url" 2>/dev/null || echo unknown)"
        echo "battery: $(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)%"
        echo "frontlight: $(lipc-get-prop com.lab126.powerd flIntensity 2>/dev/null)"
        tail -n 5 "$LOG" 2>/dev/null
        ;;
    toggle)
        load_config
        toggle_orientation
        echo "orientation: $ORIENTATION (takes effect at the next refresh or tap)"
        ;;
    *)
        echo "usage: $0 start|stop|once|status|toggle" >&2
        exit 2
        ;;
esac
