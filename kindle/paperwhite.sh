#!/bin/sh
# Paperwhite Weather: Kindle client.
# Runs as root on a jailbroken Kindle (BusyBox ash). Fetches the dashboard frame from the
# server, paints it with eips, toggles orientation on a tap, asks the server for the next
# skin on a long press, repeats.
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
# Usage: paperwhite.sh start|stop|once|status|toggle|next-skin|enable-boot|disable-boot
#        (loop and boot: internal, used by start and by the upstart job)
#
# Power: after each refresh the device stays awake AWAKE_SECONDS for taps, then suspends
# with an RTC alarm for the next refresh (SUSPEND="yes"). A tap while suspended does
# nothing; the power button wakes the device and opens a new tap window.
#
# Boot: enable-boot writes an upstart job on the (read-only, mntroot-toggled) root
# filesystem that runs "paperwhite.sh boot" once the stock framework has started: wait for
# Wi-Fi, then start. disable-boot removes the job. A firmware update would remove it too.

BASE="/mnt/us/paperwhite"
CONFIG="$BASE/config"
STATE="$BASE/state"
CACHE="$BASE/cache"
LOG="$BASE/paperwhite.log"
PIDFILE="$STATE/paperwhite.pid"
SELF="$BASE/paperwhite.sh"
UPSTART_JOB="/etc/upstart/paperwhite.conf"
EIPS="/usr/sbin/eips"
TOUCH_DEVICE="/dev/input/event1"

# Defaults; the config file overrides them.
SERVER_HOST=""
SERVER_PORT="8765"
SERVER_URL=""
REFRESH_MINUTES="15"
FULL_REFRESH_EVERY="4"
TAP_WINDOW_SECONDS="60"
SUSPEND="yes"
AWAKE_SECONDS="90"
LONG_PRESS_SECONDS="2"
STOP_FRAMEWORK="yes"
FRONTLIGHT="0"
LOG_LINES="500"
RTC_WAKEALARM="/sys/class/rtc/rtc0/wakealarm"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
    if [ "$(wc -l < "$LOG")" -gt "$LOG_LINES" ]; then
        tail -n "$LOG_LINES" "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    fi
}

positive_int_or() {
    # $1: value, $2: default. Echoes $1 if it is a whole number >= 1, else $2 (and logs).
    case "$1" in
        ''|*[!0-9]*|0*) log "config: invalid number '$1', using $2"; printf '%s\n' "$2" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

load_config() {
    mkdir -p "$STATE" "$CACHE"
    # shellcheck disable=SC1090
    [ -f "$CONFIG" ] && . "$CONFIG"
    [ -n "$PAPERWHITE_SERVER" ] && SERVER_HOST="$PAPERWHITE_SERVER"
    # Arithmetic on a bad value would abort ash (divide by zero) or busy-loop (non-number).
    REFRESH_MINUTES="$(positive_int_or "$REFRESH_MINUTES" 15)"
    FULL_REFRESH_EVERY="$(positive_int_or "$FULL_REFRESH_EVERY" 4)"
    TAP_WINDOW_SECONDS="$(positive_int_or "$TAP_WINDOW_SECONDS" 60)"
    AWAKE_SECONDS="$(positive_int_or "$AWAKE_SECONDS" 90)"
    LONG_PRESS_SECONDS="$(positive_int_or "$LONG_PRESS_SECONDS" 2)"
    case "$SUSPEND" in yes|no) ;; *) SUSPEND="yes" ;; esac
    SERVER_PORT="$(positive_int_or "$SERVER_PORT" 8765)"
    case "$FRONTLIGHT" in ''|*[!0-9]*) FRONTLIGHT="0" ;; esac
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
    rm -f "$STATE/scan_hit"  # a scan interrupted by stop could leave a stale hit behind
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

# Touch events are 16 bytes: seconds, microseconds, type | code << 16, value. The
# controller reports BTN_TOUCH (type 1, code 330) with value 1 when a finger lands and 0
# when it lifts. The kernel queues events only for readers that hold the device open, so
# one gesture is read through a single descriptor (fd 3) opened by wait_for_tap and closed
# by drain_touch; opening the device per read would drop the events in between.

read_event() {
    # Reads one event from fd 3 within $1 seconds into $CACHE/event; 1 on timeout.
    timeout "$1" dd bs=16 count=1 of="$CACHE/event" <&3 2>/dev/null && [ -s "$CACHE/event" ]
}

event_is_touch() {
    # $1: 1 for a finger landing, 0 for lifting. Tests the event in $CACHE/event.
    # shellcheck disable=SC2046 # od prints four unsigned words; split on purpose
    set -- $(od -An -v -tu4 -w16 "$CACHE/event") "$1"
    [ "$#" -eq 5 ] && [ $(( $3 % 65536 )) -eq 1 ] && [ $(( $3 / 65536 )) -eq 330 ] \
        && [ "$4" -eq "$5" ]
}

wait_for_tap() {
    # Blocks up to $1 seconds; returns 0 when a finger lands (fd 3 stays open for the rest
    # of the gesture), 1 on timeout. A lift or movement seen without its landing (the
    # loop was painting when the finger arrived) is not a gesture and is skipped.
    [ -e "$TOUCH_DEVICE" ] || { sleep "$1"; return 1; }
    exec 3< "$TOUCH_DEVICE"
    deadline=$(( $(date +%s) + $1 ))
    while :; do
        left=$(( deadline - $(date +%s) ))
        [ "$left" -gt 0 ] || { exec 3<&-; return 1; }
        read_event "$left" || continue
        event_is_touch 1 && return 0
    done
}

press_is_long() {
    # Called right after wait_for_tap. Returns 0 when the finger is still down
    # LONG_PRESS_SECONDS later, 1 as soon as it lifts. Clock granularity is one second, so
    # a hold of LONG_PRESS_SECONDS to LONG_PRESS_SECONDS+1 counts as long.
    start="$(date +%s)"
    while [ $(( $(date +%s) - start )) -lt "$LONG_PRESS_SECONDS" ]; do
        read_event 1 || continue
        event_is_touch 0 && return 1
    done
    return 0
}

http_post() {
    # POST with an empty body to $1; prints the response body. curl ships with the
    # firmware (the jailbreak used it); BusyBox wget here has no --post-data.
    if command -v curl > /dev/null 2>&1; then
        curl -s -m 15 -X POST "$1" 2>/dev/null
    else
        log "post: curl not found; cannot $1"
        return 1
    fi
}

next_skin() {
    # Ask the server for the skin after the current one; the frame is fetched afterwards.
    server="$(discover)" || { log "skin: no server found"; return 1; }
    answer="$(http_post "$server/skin/next")" || return 1
    log "skin: $(printf '%s' "$answer" | tr -d '\n' | head -c 80)"
}

drain_touch() {
    # Swallow the rest of the gesture so one tap does not count twice, then release fd 3.
    timeout 1 dd bs=16 count=64 <&3 > /dev/null 2>&1
    exec 3<&-
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

# --- suspend -------------------------------------------------------------------------

can_suspend() {
    [ "$SUSPEND" = "yes" ] && [ -w "$RTC_WAKEALARM" ] && [ -w /sys/power/state ]
}

suspend_until() {
    # $1: epoch seconds. Sets the RTC alarm and suspends; returns after resume.
    now="$(date +%s)"
    [ "$1" -gt $((now + 5)) ] || { log "suspend: deadline too close ($(( $1 - now ))s)"; return 1; }
    echo 0 > "$RTC_WAKEALARM" 2>/dev/null
    echo "$1" > "$RTC_WAKEALARM" 2>/dev/null || { log "suspend: cannot set wakealarm"; return 1; }
    log "suspend for $(( $1 - now ))s (battery $(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)%)"
    sync
    echo mem > /sys/power/state 2>/dev/null || { log "suspend: echo mem failed"; return 1; }
    log "resumed"
    return 0
}

wait_for_wifi() {
    # Up to $1 seconds for wifid to report CONNECTED after a resume.
    i=0
    while [ "$i" -lt "$1" ]; do
        [ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = "CONNECTED" ] && return 0
        sleep 1; i=$((i + 1))
    done
    log "wifi: not connected after $1s"
    return 1
}

# --- start at boot -------------------------------------------------------------------

boot_enabled() {
    [ -f "$UPSTART_JOB" ]
}

with_writable_root() {
    # Run "$@" with the root filesystem writable; mntroot is the stock Kindle tool for it.
    mntroot rw > /dev/null 2>&1 || { echo "cannot make the root filesystem writable" >&2; return 1; }
    "$@"
    rc=$?
    mntroot ro > /dev/null 2>&1
    [ "$rc" -eq 0 ] || echo "$* failed on the root filesystem (exit $rc)" >&2
    return "$rc"
}

write_upstart_job() {
    cat > "$UPSTART_JOB" <<EOF
# Paperwhite Weather: start the dashboard client at boot.
# Written by "$SELF enable-boot"; remove with "$SELF disable-boot".
start on started framework
task
exec $SELF boot
EOF
}

# --- main loop -----------------------------------------------------------------------

run_loop() {
    trap 'exit 0' INT TERM
    take_screen
    cycle=0
    while :; do
        wait_for_wifi 30
        if fetch_frame; then result="fresh"; else result="cached"; fi
        if [ $((cycle % FULL_REFRESH_EVERY)) -eq 0 ]; then paint full; else paint partial; fi
        log "refresh: $result $ORIENTATION (battery $(lipc-get-prop com.lab126.powerd battLevel 2>/dev/null)%)"
        cycle=$((cycle + 1))
        deadline=$(( $(date +%s) + REFRESH_MINUTES * 60 ))
        # Awake window: read taps for AWAKE_SECONDS (or until the deadline), then suspend
        # until the deadline if allowed, otherwise keep reading taps until then.
        while :; do
            now="$(date +%s)"
            remaining=$(( deadline - now ))
            [ "$remaining" -gt 0 ] || break
            if can_suspend && [ "$awake_until" ] && [ "$now" -ge "$awake_until" ]; then
                if suspend_until "$deadline"; then
                    # An early resume (power button) gets a fresh tap window.
                    awake_until=$(( $(date +%s) + AWAKE_SECONDS ))
                else
                    # Could not suspend: stay awake reading taps until the deadline.
                    awake_until="$deadline"
                fi
                continue
            fi
            [ "$awake_until" ] || awake_until=$(( now + AWAKE_SECONDS ))
            window="$TAP_WINDOW_SECONDS"
            [ "$remaining" -lt "$window" ] && window="$remaining"
            if can_suspend; then
                until_awake=$(( awake_until - now ))
                [ "$until_awake" -lt "$window" ] && window="$until_awake"
                [ "$window" -gt 0 ] || window=1
            fi
            if wait_for_tap "$window"; then
                if press_is_long; then next_skin; else toggle_orientation; fi
                drain_touch
                fetch_frame
                paint full
                cycle=0
                awake_until=$(( $(date +%s) + AWAKE_SECONDS ))
            fi
        done
        awake_until=""
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
    boot)
        # Run by the upstart job right after the stock framework starts; Wi-Fi is still
        # connecting, and the first fetch falls back to the cached frame if it takes longer.
        load_config
        log "boot: waiting for Wi-Fi"
        wait_for_wifi 120 || true
        exec "$SELF" start
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
        if boot_enabled; then echo "start at boot: enabled"; else echo "start at boot: disabled"; fi
        tail -n 5 "$LOG" 2>/dev/null
        ;;
    next-skin)
        next_skin && echo "asked the server for the next skin (shown at the next refresh or tap)"
        ;;
    toggle)
        load_config
        toggle_orientation
        echo "orientation: $ORIENTATION (takes effect at the next refresh or tap)"
        ;;
    enable-boot)
        with_writable_root write_upstart_job && {
            log "start at boot enabled"
            echo "start at boot enabled ($UPSTART_JOB)"
        }
        ;;
    disable-boot)
        if boot_enabled; then
            with_writable_root rm -f "$UPSTART_JOB" && {
                log "start at boot disabled"
                echo "start at boot disabled"
            }
        else
            echo "start at boot was not enabled"
        fi
        ;;
    *)
        echo "usage: $0 start|stop|once|status|toggle|next-skin|enable-boot|disable-boot" >&2
        exit 2
        ;;
esac
