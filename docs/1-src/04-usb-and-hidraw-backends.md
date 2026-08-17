# USB and Hidraw Backends

## Goal

Expand direct userspace controller support by adding focused backend modules for
USB and hidraw protocol families.

## Baseline

Current direct-controller paths include ITE 8291r3, ITE 8910, experimental ITE
8297, and the auxiliary ITE 8233 lightbar work.

## Problem breakdown

Supporting more direct-controller devices typically means one of:

1. New USB VID/PID for the same controller/protocol
2. Same VID/PID but firmware differences (quirks)
3. Different controller revision or different USB / hidraw protocol
4. Secondary device on the same chassis that should not be folded into the keyboard backend

## Approach

- Prefer **new backend modules** (or small variants) rather than growing one backend into a large if/else blob.
- Keep backends small and focused:
  - one package per controller or protocol family

## Detection

- Probe should check for relevant USB devices.
- Avoid opening endpoints in probe unless needed.

For ITE-like devices:

- Look for known VID/PID tuples.
- Record detected USB IDs in diagnostics.
- Prefer hidraw feature-report transport when that is the stable userspace path.

## Quirk handling

When a device is “almost compatible”:

- Prefer a small quirk table keyed by VID/PID or DMI strings.
- Keep quirk tables near the backend implementation.

## Per-key layout

Matrix dimensions and mapping vary by chassis.

- `dimensions()` should represent the LED matrix.
- Physical key layout is handled by calibration + profile mapping.

## Contribution workflow

When adding a new controller or chassis variant:

1. Collect:
   - `lsusb -nn`
   - DMI strings
   - whether sysfs LEDs exist
2. Decide backend type:
   - sysfs backend if present
   - direct USB / hidraw backend otherwise
3. Add probe rules + a minimal “smoke path” (brightness/uniform)
4. Validate per-key only after confirming matrix + calibration.

If the device is auxiliary-only, keep it as a separate surface instead of
forcing keyboard-only abstractions to own it.

## Managed udev rules

Installer-managed permission rules live under `system/udev/`:

- `99-ite8291-wootbook.rules` (USB/hidraw uaccess)
- `99-keyrgb-sysfs-leds.rules`
- `99-keyrgb-input-uaccess.rules`

Each file carries a stable `KEYRGB_MANAGED_UDEV_RULE=...` marker. Uninstall
matching (`scripts/lib/uninstall_match.sh`) removes a rule when either:

1. the installed file exactly matches the repo/bootstrap source copy, or
2. the installed file contains the stable managed marker (or a documented legacy
   header marker from older releases).

Bootstrap curl uninstalls often lack the `system/udev` source tree, so marker
matching alone must be enough. Do not identify managed rules only by stale
comment text that can drift when headers are rewritten.

## Testing

- Unit tests for selection and probe logic.
- Optional hardware tests behind `KEYRGB_HW_TESTS=1`.
- Installer uninstall matching tests under `tests/installer/`.
