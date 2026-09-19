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

Still open for Sprint 3: whether the stock GUI repaints over our frame and how to stop it
(`stop framework` vs. painting on top), screensaver suppression, suspend and RTC wake, and
the rotation direction of the landscape frame as mounted on the wall.

Anything in `kindle/` is a **draft** until it has been run on the device, and its header
says so.

## Handling notes

- Never delete or modify anything under `/media/smokingpi/Kindle/system` from the Pi; the
  device's own software owns it.
- Unmount (`udisksctl unmount -b /dev/sda1`) before unplugging the USB cable.
