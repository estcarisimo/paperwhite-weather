# Device notes

What is known about the target Kindle, split into **verified** (with the command and date)
and **assumed** (from public specifications or community documentation, still to be
confirmed on the device). Do not move an item to "verified" without evidence.

## Verified on 2026-09-18 (device connected over USB to the Raspberry Pi)

| Fact | Value | Evidence |
| --- | --- | --- |
| USB identity | `1949:0004 Lab126, Inc. Amazon Kindle 3/4/Paperwhite` | `lsusb` |
| Serial prefix | `G090G1…` | `cat /sys/bus/usb/devices/1-1/serial` |
| Firmware | `Kindle 5.16.2.1.1 (409747 002)` | `cat /media/smokingpi/Kindle/system/version.txt` |
| User storage | 3.1 GB, 360 KB used | `df -h /media/smokingpi/Kindle` |
| Mount point on the Pi | `/media/smokingpi/Kindle` (`/dev/sda1`, label `Kindle`) | `lsblk` |
| Content (before jailbreak) | Empty `documents/`, stock `system/`; no jailbreak files present | `ls -la /media/smokingpi/Kindle` |

## Verified on 2026-09-19 over SSH (after the jailbreak; see the runbook below)

| Fact | Value | Evidence |
| --- | --- | --- |
| Jailbreak | WinterBreak2, `jb.sh v1.3.7` | `documents/JAILBROKEN.txt` |
| Kernel | `Linux kindle 3.0.35-lab126 #8 PREEMPT Tue Aug 1 12:49:59 UTC 2023 armv7l` | `uname -a` |
| Firmware string | `Kindle 5.16.2.1.1` | `cat /etc/prettyversion.txt` |
| **Panel** | `xres 1072, yres 1448`, `bits_per_pixel 8`, `grayscale 1`, `line_length 1088`, driver `mxc_epdc_fb` | `/usr/sbin/eips -i` |
| `eips` | `/usr/sbin/eips` (not on the default `PATH=/usr/bin:/bin`; call it by full path) | `ls -la /usr/sbin/eips` |
| FBInk | `/mnt/us/usbnet/bin/fbink` (symlinked to `/usr/bin/fbink`) and `/mnt/us/libkh/bin/fbink` from the jailbreak; `fbink -e` segfaulted on the usbnet build, not investigated | `ls -la`, `fbink -e` |
| `wget`, `curl` | `/usr/bin/wget`, `/usr/bin/curl` | `which` |
| `lipc-get-prop`, `lipc-set-prop` | `/usr/bin/` | `which` |
| `rtcwake` | missing; RTC wake is via `/sys/class/rtc/rtc0/wakealarm` (`max77696-rtc.0`; `rtc1`, `rtc2` also present) | `which rtcwake`, `ls /sys/class/rtc/rtc0/` |
| **Touch controller** | `/dev/input/event1`, name `cyttsp4_mt`; `event0` is the power button (`max77696-onkey`) | `cat /proc/bus/input/devices` |
| Tap readable with the stock GUI running | yes: `timeout 15 dd if=/dev/input/event1 bs=16 count=4` returned `BTN_TOUCH` (type 1, code 0x14a) followed by `ABS_MT_*` events on a tap | `od` dump, 2026-09-19 |
| Event struct | 16 bytes: 8 bytes of timestamp, 2-byte type, 2-byte code, 4-byte value | `od -t x1` dump |
| Wi-Fi | `CONNECTED`, `192.168.86.51/24`, resolver `nameserver 192.168.86.1`, `domain lan` | `lipc-get-prop com.lab126.wifid cmState`, `ip addr`, `/etc/resolv.conf` |
| **Discovery from the device** | `wget -q -O - http://smokingpi.lan:8765/health` returned the service identity JSON | run over SSH, 2026-09-19 |
| **First frame on the panel** | `wget http://smokingpi.lan:8765/dashboard.png && /usr/sbin/eips -c && /usr/sbin/eips -g /mnt/us/dashboard.png` painted the landscape frame (`update_mode=PARTIAL, wave_mode=2`) | run over SSH, 2026-09-19 |
| Device hostname | `kindle`; the router did **not** resolve `kindle.lan`, so the Kindle is found by IP or by scanning | `cat /etc/hostname`, `getent hosts kindle.lan` on the Pi |
| Battery | 99 % | `lipc-get-prop com.lab126.powerd battLevel` |
| powerd | `state active`, `preventScreenSaver 0` | `lipc-get-prop com.lab126.powerd ...` |
| Memory | 502 MB total, ~200 MB free | `free -m` |
| User storage after everything | 553 MB free of 3.0 GB (five filler files still in place) | `df -h /mnt/us` |

## Model

**Kindle Paperwhite 3 (7th generation, 2015).** Serial prefix `G090G1` per the community
serial tables, and the panel geometry reported by `eips -i` (1072x1448, 8-bit grayscale)
matches that model. The default `display.width` / `display.height` in `config.py` are
therefore verified for this device.

## Jailbreak runbook (executed 2026-09-18/19; all steps done)

**Legal and warranty note.** Jailbreaking modifies the software of a device you own. It
likely breaches Amazon's Kindle terms of use, voids any remaining warranty, and can brick
the device if done wrong; whether it is lawful depends on your jurisdiction (in the United
States, DMCA exemptions have covered unlocking of consumer devices, but this project makes
no legal claim). This repository documents the procedure and links to the community
tools; it does **not** redistribute Amazon firmware or the jailbreak binaries. You act on
your own device at your own risk.

Route selection comes from the KindleModding jailbreak wizard's data file
(`static/jailbreaks.json` in `KindleModding/kindlemodding.github.io`, read 2026-09-18). For
model **PW3** on firmware **5.16.2.1.1** two routes apply:

| Route | Firmware range | Registration to an Amazon account | Release used | How the exploit is triggered |
| --- | --- | --- | --- | --- |
| **WinterBreak2** (preferred) | 5.6.1.1 – 5.16.3 | not required | v1.1.0, 2026-08-22 | Experimental Browser opens `https://penguins184.xyz/wb2` |
| WinterBreak (fallback) | 5.6.1.1 – 5.18.0.2 | **required** | v2.1.0, 2026-06-28 | Kindle Store opens Mesquito, tap the WinterBreak icon |

Both routes install the jailbreak hotfix and block OTA updates as part of the process
(the post-jailbreak pages say to skip those steps for WinterBreak/SpringBreak/Sanctuary
users). Both need Wi-Fi at the moment of the exploit.

**Risk to manage: an over-the-air update.** The device is on 5.16.2.1.1 and Amazon ships
newer firmware for this model. When the Kindle joins Wi-Fi it may download an update, and
a firmware above 5.16.3 closes the preferred route. Mitigation, from the KindleModding
"prevent auto update" page: leave only 50–90 MB free on the USB partition so the updater
cannot download. Reversible by deleting the filler files afterwards.

### Steps

Done from the Pi (device mounted at `/media/smokingpi/Kindle`), **executed 2026-09-18**:

1. Filled the USB partition: `fill_disk/` with seven dummy files (`dd if=/dev/zero`,
   500 MB each, the last one smaller); free space went from 3.1 GB to **70 MB**
   (`df -h`).
2. Checked for `*.bin` or `update.bin.tmp.partial` on the USB root: none present.
3. Extracted `wb2.zip` (WinterBreak2 v1.1.0, SHA-256
   `9e85970902a1f2af6b4c3243755d80595dd36404b85083f8be8c65a69d04cfdf`) to the USB root,
   producing `winterbreak2/dialoger.html` (627 bytes; checksum on the device matches the
   download). The file asks the device's transfer service to run
   `curl -L https://kindlemodding.org/jb.sh | sh`; that script is the jailbreak.
4. Unmounted: `udisksctl unmount -b /dev/sda1`.

Done on the device by the maintainer, **2026-09-18**:

5. Unplugged USB, joined the home Wi-Fi.
6. Home → menu → **Experimental Browser** → `https://penguins184.xyz/wb2` → **Jailbreak**.
7. Result: `documents/JAILBROKEN.txt` ("You are jailbroken! (jb.sh v1.3.7) Winterbreak2
   Jailbreak") and `libkh/bin/fbink` on the USB partition; two crash reports from the
   exploited app in `documents/` (expected; they can be deleted). The WinterBreak
   fallback (registered device, Kindle Store → Mesquito) was not needed.
8. Plugged USB back in.

Done from the Pi, **2026-09-19** (checksums matched the downloads):

9. **KUAL**: `KUAL.sh` and `KUAL.jar` from `PEKI.zip` (`KindleTweaks/PEKI` v1.0,
   SHA-256 `f653045909ed230496c3d8176c9901d3a6a1f693c52b488569be6a60e0852499`) to
   `documents/`.
10. **MRPI** 1.7.N r19303 ("Patched for FW >= 5.16.3", works on 5.16.2.1.1):
    `kual-mrinstaller-khf.zip` from kindlemodding.org (SHA-256
    `9974dfc2d1e7687b3fc74d68f6b5aeab2428f22d83ab82e6d600a0384c607d09`); its `extensions/`
    and `mrpackages/` to the USB root. Two filler files deleted first (611 MB free).
11. **USBNetwork** 0.22.N r19297 (NiLuJe, MobileRead thread 225030;
    `kindle-usbnet-0.22.N-r19297.tar.xz`, SHA-256
    `cf971557d42cc0a6d7699f1c743108c681fa41e3d67ee5802a91932d130d4032`):
    `Update_usbnet_0.22.N_install_pw2_and_up.bin` into `mrpackages/`. The `usbnetlite`
    alternative was skipped because its release notes require firmware 5.16.3 or later.
    On the device: KUAL → Helper → *Install MR Packages*. The MRPI log ended with
    `Success! :)` followed by "Really failed to remount rootfs RO", which is a known
    harmless message from this MRPI build; the device then restarted.
12. **SSH over Wi-Fi**, from the Pi: the Pi's public key into
    `usbnet/etc/authorized_keys`; in `usbnet/etc/config`: `USE_WIFI="true"`,
    `USE_WIFI_SSHD_ONLY="true"` (SSH only over Wi-Fi; USB stays mass storage so files can
    still be edited from the Pi); `usbnet/DISABLED_auto` renamed to `usbnet/auto` so it
    starts at boot. After a restart the Kindle answered on port 22 (dropbear) at
    `192.168.86.51`; `ssh root@192.168.86.51` with the key works. Login is `root`; the
    password is not used.
13. Not yet done: delete `fill_disk/` (five files remain), confirm OTA blocking with the
    *Check OTA Status* scriptlet, delete the crash reports from `documents/`.

The Kindle's DHCP hostname is `kindle` and this router does not resolve it, so the Pi
finds the device by scanning the LAN for port 22 (or use a DHCP reservation on the
router). That is the opposite direction from the dashboard traffic and only matters for
development.

Everything the runbook asked to record after shell access is in the "Verified on
2026-09-19" table above. The touch findings there confirm the community description
(SixFoisNeuf, "Kindle hacking: a deeper dive into the internals") of 16-byte input events
on `/dev/input/event1`, and add that the events reach a script while the stock GUI is
running. What the stock GUI does to our frame afterwards is a Sprint 3 question: a tap
made it repaint its home screen over the frame on 2026-09-19, so the client will need to
stop the framework or keep repainting.

## Kindle-side runtime (verified 2026-09-19)

| Tool | Where | Use |
| --- | --- | --- |
| `eips` | `/usr/sbin/eips` (full path needed) | `eips -c` clears the panel; `eips -g file.png` paints an image; `eips -i` prints panel info |
| `wget` | `/usr/bin/wget` | Download the PNG from `http://<server>.lan:8765/` over plain HTTP (verified) |
| `curl` | `/usr/bin/curl` | Alternative to `wget` |
| `lipc-set-prop` / `lipc-get-prop` | `/usr/bin/` | Wi-Fi state, screensaver, battery (verified reads) |
| RTC wake | `/sys/class/rtc/rtc0/wakealarm` (`rtcwake` is absent) | Wake from suspend on a timer; not exercised yet |
| Touch | `/dev/input/event1` (`cyttsp4_mt`), 16-byte events | Tap detection; verified readable with the stock GUI running |
| FBInk | `/usr/bin/fbink` (usbnet) | Optional alternative to `eips`; the usbnet build crashed on `-e`, so `eips` is the tool for now |
| `powerd` | via lipc | Must be told not to blank the screen or suspend on its own (Sprint 3) |

## Client behavior verified on 2026-09-19 (`kindle/paperwhite.sh`, over SSH)

| Fact | Evidence |
| --- | --- |
| `stop framework` stops the stock GUI (`initctl list` → `framework stop/waiting`); `lab126_gui`, `pillow`, `x`, `powerd`, `wifid` keep running; Wi-Fi stays `CONNECTED` | `initctl list`, `lipc-get-prop com.lab126.wifid cmState` after the stop |
| With the GUI stopped, `eips -g` paints and the frame stays on the panel; nothing repaints over it | framebuffer capture with `fbgrab` 15 minutes later matched the served frame |
| Touch events still arrive on `/dev/input/event1` with the GUI stopped | `timeout 60 dd if=/dev/input/event1 bs=16 count=1` returned on a synthetic tap |
| A tap toggles orientation and repaints: landscape → portrait → landscape | two `evemu-event ... BTN_TOUCH` injections; `paperwhite.log` shows both toggles, `state/orientation` follows |
| Frontlight is `com.lab126.powerd flIntensity` (0–24); it was at 22 with the GUI stopped and no way to reach the slider, so the client sets it to `FRONTLIGHT` (0) on start and restores the saved level on stop | `lipc-get-prop`/`lipc-set-prop com.lab126.powerd flIntensity` |
| `preventScreenSaver` 1/0 is honored | `lipc-get-prop com.lab126.powerd preventScreenSaver` after start/stop |
| `screenSaverTimeout` does not exist on this firmware (`lipcErrNoSuchProperty`) | `lipc-get-prop com.lab126.powerd screenSaverTimeout` |
| A shell trap cannot run while the shell waits on the touch read, so `stop` kills the loop's session (`setsid`, `kill -TERM -- -PID`) and does the restore itself | first `stop` implementation left the GUI stopped; fixed and re-tested |
| Backgrounding a function inherits the parent's `$$`, so the loop runs as `paperwhite.sh loop` under `setsid` and writes its own PID | first `start` wrote a dead PID; fixed and re-tested |
| Bad numeric config values (`REFRESH_MINUTES="fifteen"`, `FULL_REFRESH_EVERY="0"`, empty, `x`) fall back to the defaults with a log line instead of aborting ash (divide by zero) or busy-looping | run under `busybox ash` on the Pi with a patched `BASE`; reviewer reproduced the crash on the previous revision |
| Discovery: `http://smokingpi.lan:8765` answered `/health` on the first candidate; `wget` of `/dashboard/landscape.png` took under a second | `sh -x paperwhite.sh once` |
| `ip route`, `awk`, `timeout`, `dd`, `setsid`, `nohup`, `evemu-event`, `fbgrab` present | `which`; `evemu`/`fbgrab` come with USBNetwork |
| `fbgrab /mnt/us/screen.png` captures the panel as a 1072x1448 PNG | run over SSH |

## Long press verified on 2026-09-20 (`kindle/paperwhite.sh`, synthetic events over SSH)

| Verified | Evidence |
| --- | --- |
| `curl` 7.86.0 is on the stock firmware (`/usr/bin/curl`); BusyBox 1.34.1 `wget` has no `--post-data`, so the client posts with `curl` | `command -v curl`, `wget` usage text |
| A 3 s `BTN_TOUCH` press/release asks the server for the next skin; the frame is refetched; orientation unchanged | `evemu-event … BTN_TOUCH --value 1`, `sleep 3`, `--value 0`: `paperwhite.log` `skin: {"skin": "graphic"}` 2 s after the press; `state/orientation` unchanged; `/health` on the server reports the new skin |
| A tap still toggles orientation, in the same second | two taps: `orientation: portrait`, then `landscape`, each logged at the tap's second |
| A 1 s hold is a tap, not a long press (`LONG_PRESS_SECONDS` 2) | press, `sleep 1`, release: `orientation: portrait` logged, no skin change |
| The gesture is read through one open descriptor; with the device reopened per read (the first implementation) evdev dropped the events in between and a tap whose lift fell in a gap, or whose landing arrived while the loop was painting, counted as a hold | first run: two taps logged as `skin:` changes; after the fix (fd 3 held from landing to drain): the four gestures above, all correct, twice |
| The server answers `POST /skin/next` at once; before PR #31's background persistence it took up to 15 s on this Pi under load, and the Kindle's follow-up tap was swallowed by the late drain | `curl -sv -X POST` from the device: 0 s after, 15 s timeout before |
| Suspend and wake unchanged: the awake window is extended by each gesture as by a tap; the next `suspend for … s` line follows | `paperwhite.log` after the test |

## Power: measured and verified on 2026-09-19

| Fact | Evidence |
| --- | --- |
| Awake with Wi-Fi on, 15-minute refreshes: **95 % → 77 % in 13.8 h, about 1.3 %/h**, roughly three days per charge | `battery.log` on the device, 01:54 UTC to 15:41 UTC |
| `/sys/power/state` offers `standby mem`; `/sys/class/rtc/rtc0/wakealarm` is writable; RTC and system clocks agree to the second | `cat`, `since_epoch` vs `date +%s` |
| `echo <epoch> > wakealarm; echo mem > /sys/power/state` suspends within 2 s and resumes on the alarm to the second | 90 s test: SSH dropped at +2 s, back at +90 s; on-device log `resumed at 15:43:30` for an alarm at 15:43:29 |
| Wi-Fi is `CONNECTED` immediately after resume; a fetch by DNS name succeeded 0.02 s later | `lipc-get-prop com.lab126.wifid cmState`, `time wget .../health` |
| The client's cycle works: refresh, 40 s awake, `suspend for 80s`, `resumed`, re-fetch 5 s after resume | `paperwhite.log` with `REFRESH_MINUTES=2`, `AWAKE_SECONDS=40`; `current.png` mtime |
| The stock GUI stays stopped and `preventScreenSaver` stays 1 across suspend/resume | `initctl list`, `lipc-get-prop` after resume |
| `otaupd` is renamed to `/usr/bin/otaupd.bck`, so OTA updates are blocked (done by WinterBreak2) | `ls /usr/bin/otaup*` |
| `fill_disk/`, `winterbreak2/`, and the exploit's crash reports deleted; 3.0 GB free | `df -h /mnt/us` |
| `paperwhite.sh enable-boot` writes `/etc/upstart/paperwhite.conf` (`start on started framework`, `task`, `exec … boot`) with `mntroot rw`/`ro`, root back to `ro` afterwards; after `reboot` the job ran `boot` at +57 s, Wi-Fi was connected 9 s later, and the loop painted a fresh frame with the GUI stopped at +68 s, with no command from outside | `mount`, `paperwhite.log` after the reboot (`boot: waiting for Wi-Fi` … `framework stopped` … `refresh: fresh`), `status`, `initctl status framework` → `stop/waiting` |

Battery with suspend is being measured from 2026-09-19 15:49 UTC at 77 %; the client logs
the level on every refresh (`refresh: fresh landscape (battery 77%)`). First reading: still
77 % after one hour, 76 % after two (including a reboot).

Still open: the rotation direction of the landscape frame as physically mounted.

`kindle/install.sh` is still a **draft**; the client was installed over SSH.

## Handling notes

- Never delete or modify anything under `/media/smokingpi/Kindle/system` from the Pi; the
  device's own software owns it.
- Unmount (`udisksctl unmount -b /dev/sda1`) before unplugging the USB cable.
