# Diagnostics, Discovery, and Identity

## Goal

Make it easy for users to provide the right evidence to confirm support,
triage backend selection, or add a new controller path.

## Data to collect

### USB identifiers

- `lsusb -nn`
- If possible: filter for likely devices (ITE often shows as `048d:....` but do not assume)

### DMI (chassis identity)

Read from:

- `/sys/class/dmi/id/sys_vendor`
- `/sys/class/dmi/id/product_name`
- `/sys/class/dmi/id/board_name`

These strings are often useful for heuristics, support triage, and quirk rules.

### Sysfs backlight nodes

- `ls /sys/class/leds`
- look for `kbd`, `keyboard`, `backlight`

### Hidraw and discovery data

- hidraw device nodes and report-descriptor availability
- backend probe outcomes and reasons
- detected auxiliary devices such as a lightbar path

### Environment / conflicts

- Desktop environment (GNOME/KDE/etc)
- Other RGB tools running (OpenRGB, vendor daemons)

## Current support surface

- Support Tools window from the tray
- Saved diagnostics JSON, discovery JSON, and support bundles
- Suggested issue drafts and backend-speed probe notes
- DEBUG logging for deeper local investigation

## Privacy

DMI strings can include model identifiers.

- Treat diagnostics as “user chooses to share”.
- Do not auto-upload anything.

## How this helps support

When a user opens an issue, the maintainer can:

- pick sysfs backend if nodes exist
- pick USB backend if VID/PID matches
- add a quirk rule if DMI indicates a known family or chassis pattern
- tell whether the device is supported, experimental-disabled, dormant, or unrecognized
- request deeper evidence only when the safe discovery path is insufficient