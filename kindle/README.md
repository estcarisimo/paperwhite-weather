# Kindle-side client

Everything here runs as root on a jailbroken Kindle (BusyBox `ash`). `paperwhite.sh` was
verified on a Paperwhite 3 with firmware 5.16.2.1.1 on 2026-09-19; `docs/DEVICE.md` has the
evidence. `install.sh` is still a draft (the maintainer installed over SSH).

| File | Purpose |
| --- | --- |
| `paperwhite.sh` | The client: discover the server, fetch the frame for the current orientation, paint it with `eips`, toggle orientation on a tap, repeat every `REFRESH_MINUTES` |
| `config.example` | Client configuration; becomes `/mnt/us/paperwhite/config` on the device |
| `extensions/paperwhite/` | KUAL extension: Start, Stop, Show one frame, Toggle orientation, Status |
| `install.sh` | Copies the above to a USB-mounted Kindle and writes the config with your server's hostname |

## Install

Over USB (draft):

```bash
kindle/install.sh /media/<you>/Kindle <server-hostname>
```

Over SSH (what was actually done):

```bash
K=root@<kindle-ip>
ssh $K 'mkdir -p /mnt/us/paperwhite/state /mnt/us/paperwhite/cache /mnt/us/extensions/paperwhite/bin'
scp kindle/paperwhite.sh $K:/mnt/us/paperwhite/
scp kindle/extensions/paperwhite/config.xml kindle/extensions/paperwhite/menu.json $K:/mnt/us/extensions/paperwhite/
scp kindle/extensions/paperwhite/bin/*.sh $K:/mnt/us/extensions/paperwhite/bin/
sed 's/^SERVER_HOST=.*/SERVER_HOST="<server-hostname>"/' kindle/config.example | ssh $K 'cat > /mnt/us/paperwhite/config'
ssh $K 'chmod +x /mnt/us/paperwhite/paperwhite.sh /mnt/us/extensions/paperwhite/bin/*.sh'
```

Then on the Kindle: KUAL → Paperwhite Weather → Start dashboard. Or over SSH:
`/mnt/us/paperwhite/paperwhite.sh start|stop|once|status|toggle`.

## What `start` does to the device

- Stops the stock GUI job (`stop framework`) so it cannot repaint over the frame. Wi-Fi,
  power management, and the touch controller keep running.
- Sets `preventScreenSaver 1` so the device does not blank the panel.
- Saves the frontlight level and sets it to `FRONTLIGHT` (default 0, off).
- Runs the loop in its own session (`setsid`), so it survives the shell that started it.

`stop` reverses all of that (`start framework`, screensaver guard off, frontlight restored)
and kills the loop's process group, including the blocking touch read. **With the GUI
stopped, the Kindle's own controls are unreachable**; `stop` from KUAL is not possible
either since KUAL is part of the GUI. Stop over SSH, or hold the power button for a
restart (the loop does not start at boot).

## Discovery

In order, stopping at the first `/health` that identifies as `paperwhite-weather`:
`SERVER_URL` if set; the last server that answered (`state/server_url`); then
`http://$SERVER_HOST.lan:$SERVER_PORT`, `.local`, and the bare name; then a `/24` scan of
the default gateway's subnet, 32 hosts at a time. `PAPERWHITE_SERVER` in the environment
overrides `SERVER_HOST` for one run.

## Not yet done

- Suspend between refreshes with an RTC wake (`/sys/class/rtc/rtc0/wakealarm`). The loop
  keeps the device awake with Wi-Fi on; the overnight battery measurement decides whether
  that is acceptable at 15-minute refreshes.
- Start at boot.
