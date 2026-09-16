## Issue 13: MEDION ERAZER Beast X30 (`048d:6005` / `048d:ce00`)

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/13

Status as of 2026-09-16:

- The AppImage installer exposed `keyrgb` but not the documented
  `keyrgb-diagnostics` command. The diagnostics fix adds both
  `keyrgb --diagnostics` and an installer-managed forwarding command.
- Diagnostics now retain read-only sysfs and device-node details for observed,
  unrecognized `0x048d` devices. This should capture the `bcdDevice`, product
  string, USB node permissions, and bound driver for `048d:6005`.
- `048d:6005` is **not enabled in a lighting backend yet**. The issue confirms
  that the ID exists and identifies itself as ITE 8291, but does not establish
  which ITE protocol dialect it accepts.

## Why backend enablement remains evidence-gated

The two reported devices cannot be treated as interchangeable based on their
product strings alone:

- `048d:ce00`, `bcdDevice 0x0003` uses the validated
  `ite8291r3_perkey` path.
- `048d:ce00`, `bcdDevice 0x0002` is the separate experimental 4-zone path.
- No current upstream or captured protocol evidence associates `048d:6005`
  with either command set.

Adding `6005` to a USB or hidraw allowlist before that distinction is known
could send the wrong reports to a composite input or auxiliary device.

## Evidence required from the reporter

After installing a build containing the diagnostics fix, open **Settings →
Version → Support Tools…**, run diagnostics and device discovery, and choose
**Save full support bundle…**. Attach that bundle to issue #13.

If the UI cannot be opened, collect the terminal fallback plus the two verbose
USB descriptors:

```bash
keyrgb --diagnostics
lsusb -v -d 048d:6005
lsusb -v -d 048d:ce00
```

The diagnostics JSON should keep the backend probe reasons and the safe sysfs
details for both devices. If available, also include the hidraw mappings and
report-descriptor evidence offered by **Support Tools**. Backend work can resume
once the output establishes each device's `bcdDevice`, interfaces, hidraw
mapping, permissions, and likely protocol dialect.
