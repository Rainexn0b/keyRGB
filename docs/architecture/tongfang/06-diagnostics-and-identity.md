# Diagnostics & Identity (Tongfang-focused)

## Goal

Make it easy for Tongfang users to provide the right data to add support for their keyboard.

## Data to collect

### USB identifiers

- `lsusb -nn`
- If possible: filter for likely devices (ITE often shows as `048d:....` but do not assume)

### DMI (chassis identity)

Read from:

- `/sys/class/dmi/id/sys_vendor`
- `/sys/class/dmi/id/product_name`
- `/sys/class/dmi/id/board_name`

These strings are often useful for heuristics and debugging.

### Sysfs backlight nodes

- `ls /sys/class/leds`
- look for `kbd`, `keyboard`, `backlight`

### Environment / conflicts

- Desktop environment (GNOME/KDE/etc)
- Other RGB tools running (OpenRGB, vendor daemons)

## Where to expose diagnostics

Minimal (no new UI pages required):

- Print to logs at DEBUG on startup
- Optionally provide a CLI helper later (separate scope)

## Privacy

DMI strings can include model identifiers.

- Treat diagnostics as “user chooses to share”.
- Do not auto-upload anything.

## How this helps support

When a user opens an issue, the maintainer can:

- pick sysfs backend if nodes exist
- pick USB backend if VID/PID matches
- add a quirk rule if DMI indicates a known Tongfang chassis
