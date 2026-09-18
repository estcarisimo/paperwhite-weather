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

## Jailbreak plan (not yet executed)

Firmware 5.16.2.1.1 is within the range covered by the **WinterBreak** jailbreak
(published on MobileRead in January 2025; it applies to firmware up to 5.18.1). The
expected sequence, to be re-checked against the current MobileRead thread before running:

1. Put the Kindle in **airplane mode** and keep it there until the hotfix is installed, so
   the device cannot pick up an over-the-air update mid-process.
2. Copy the WinterBreak files to the USB root from the Pi (the drive is already mounted).
3. Restart the Kindle, open the Kindle Store from the home screen; the exploit runs and
   shows a confirmation.
4. Install the **jailbreak hotfix** package, then **KUAL** (launcher) and **MRPI**
   (package installer) over USB.
5. Install **USBNetwork** to get SSH over USB (and later Wi-Fi) for development.

Items to record once done: exact package versions used, the MobileRead post revision, and
the output of `eips -i`, `uname -a`, `cat /etc/prettyversion.txt`, and `which wget curl
eips lipc-set-prop rtcwake`.

## Kindle-side runtime (assumed until shell access)

| Tool | Expected | Use |
| --- | --- | --- |
| `eips` | present in stock firmware | `eips -c` clears the panel; `eips -g file.png` paints an image; `eips -i` prints panel info |
| `wget` | BusyBox applet | Download the PNG from the LAN service (HTTP; HTTPS support on the device is uncertain) |
| `lipc-set-prop` / `lipc-get-prop` | present | Toggle Wi-Fi, prevent screensaver, read battery |
| `rtcwake` or `/sys/class/rtc/rtc*/wakealarm` | one of them | Wake from suspend on a timer |
| `powerd` | present | Must be told not to blank the screen or suspend on its own |

Anything in `kindle/` is a **draft** until it has been run on the device, and its header
says so.

## Handling notes

- Never delete or modify anything under `/media/smokingpi/Kindle/system` from the Pi; the
  device's own software owns it.
- Unmount (`udisksctl unmount -b /dev/sda1`) before unplugging the USB cable.
