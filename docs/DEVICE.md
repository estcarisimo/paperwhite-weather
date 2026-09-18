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
| Content | Empty `documents/`, stock `system/`; no jailbreak files present | `ls -la /media/smokingpi/Kindle` |

## Inferred (high confidence, confirm in Sprint 1)

- **Model: Kindle Paperwhite 3 (7th generation, 2015).** Serial numbers starting with
  `G090G1` are Paperwhite 3 units in the community serial tables, and 5.16.2.1.1 is the
  last firmware Amazon shipped for that generation. Confirm from Settings → Device Info
  or `lipc-get-prop` after shell access.
- **Panel: 6-inch, 1072x1448 pixels, 300 ppi, 16 gray levels.** From the product
  specification. Confirm with `eips -i` on the device; the framebuffer geometry it prints
  is the source of truth for `display.width` / `display.height`.

## Jailbreak runbook (verified against the sources on 2026-09-18; steps 1–4 executed)

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

Done on the device (needs hands; the maintainer):

5. Unplug USB. Settings → Wi-Fi: join the home network.
6. Home → menu (three dots) → **Experimental Browser**. Go to
   `https://penguins184.xyz/wb2`. Press **Jailbreak**. Wait for completion.
7. Check: a `Run Hotfix` booklet or a jailbreak confirmation appears in the library or on
   screen. If the browser route fails, use the WinterBreak fallback (requires the device
   to be registered): airplane mode → reboot → copy the `WinterBreak.tar.gz` contents to
   the USB root → open the Kindle Store → allow turning airplane mode off → tap the
   WinterBreak icon → wait about 30 seconds for the GUI to restart.
8. Plug USB back in for the next stage.

Done from the Pi again:

9. **KUAL** (launcher): copy `KUAL.sh` and `KUAL.jar` from `PEKI.zip`
   (`KindleTweaks/PEKI`, latest release) to `documents/`.
10. **MRPI** (package installer): extract `kual-mrinstaller-khf.zip` (from the KindleModding
    site, provided by Marek) and copy its `extensions/` and `mrpackages/` folders to the
    USB root.
11. **USBNetwork** (SSH over USB and Wi-Fi): put the MobileRead `kindle-usbnet-*.bin`
    package in `mrpackages/`, unmount, then on the device open KUAL → Helper → *Install
    MR Packages*.
12. Delete `fill_disk/` once the jailbreak is confirmed and OTA blocking is in place
    (`renameotabin` is included by WinterBreak; verify with the *Check OTA Status*
    scriptlet).

For the first on-device display test, `docs/img/minimal-landscape.png` is a landscape
frame already rotated to the portrait framebuffer, and `docs/img/minimal-portrait.png`
is the portrait one; copy either to the device and run `eips -g <file>`.

Record after step 11: `eips -i`, `uname -a`, `cat /etc/prettyversion.txt`, `which wget
curl eips lipc-set-prop lipc-get-prop rtcwake`, `ls /dev/input/`, and `cat
/proc/bus/input/devices` (which node is the touch controller). Then move the panel
geometry and the toolchain table below from "assumed" to "verified".

### Touch input (design, verify in Sprint 1)

Community notes (SixFoisNeuf, "Kindle hacking: a deeper dive into the internals") describe
`/dev/input/event0..2` on older models with 16-byte events (two 4-byte timestamp words,
2-byte type, 2-byte code, 4-byte value); the touch controller on Paperwhite-class devices
is typically `event1`. To verify: `cat /proc/bus/input/devices`, then
`timeout 10 dd if=/dev/input/event1 bs=16 count=1 | xxd` while tapping the screen. Also
check whether the stock GUI (`lab126_gui` / `framework`) must be running for touches to
register at the device node; other dashboards stop the framework and paint over it.

## Kindle-side runtime (assumed until shell access)

| Tool | Expected | Use |
| --- | --- | --- |
| `eips` | present in stock firmware | `eips -c` clears the panel; `eips -g file.png` paints an image; `eips -i` prints panel info |
| `wget` | BusyBox applet | Download the PNG from `http://<server>.lan:8765/` (plain HTTP on the LAN; HTTPS support on the device is uncertain) |
| `lipc-set-prop` / `lipc-get-prop` | present | Toggle Wi-Fi, prevent screensaver, read battery |
| `rtcwake` or `/sys/class/rtc/rtc*/wakealarm` | one of them | Wake from suspend on a timer |
| `powerd` | present | Must be told not to blank the screen or suspend on its own |

Anything in `kindle/` is a **draft** until it has been run on the device, and its header
says so.

## Handling notes

- Never delete or modify anything under `/media/smokingpi/Kindle/system` from the Pi; the
  device's own software owns it.
- Unmount (`udisksctl unmount -b /dev/sda1`) before unplugging the USB cable.
