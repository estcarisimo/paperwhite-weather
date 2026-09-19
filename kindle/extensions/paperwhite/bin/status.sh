#!/bin/sh
# KUAL menu entry: status, shown on the panel with eips for a few seconds
out="$(/mnt/us/paperwhite/paperwhite.sh status 2>&1)"
y=2
printf '%s\n' "$out" | while IFS= read -r line; do
    /usr/sbin/eips 1 "$y" "$line" > /dev/null 2>&1
    y=$((y + 1))
done
