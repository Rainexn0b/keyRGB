# USB Backends (Tongfang)

## Goal

Expand USB-based keyboard support on Tongfang laptops by adding additional backend modules for controller variants.

## Baseline

Current USB path is the ITE 8291r3-style controller via `ite8291r3-ctl`.

## Problem breakdown

Supporting “more Tongfang keyboards” via USB typically means one of:

1. New USB VID/PID for the same controller/protocol
2. Same VID/PID but firmware differences (quirks)
3. Different ITE revision or different USB protocol

## Approach

- Prefer **new backend modules** (or variants) rather than growing one backend into a large if/else blob.
- Keep backends small and focused:
  - one file per controller/protocol family

## Detection

- Probe should check for relevant USB devices.
- Avoid opening endpoints in probe unless needed.

For ITE-like devices:

- Look for known VID/PID tuples.
- Record detected USB IDs in diagnostics.

## Quirk handling

When a device is “almost compatible”:

- Prefer a small quirk table keyed by VID/PID or DMI strings.
- Keep quirk tables near the backend implementation.

## Per-key layout

Matrix dimensions and mapping vary by chassis.

- `dimensions()` should represent the LED matrix.
- Physical key layout is handled by calibration + profile mapping.

## Contribution workflow

When adding a new Tongfang model:

1. Collect:
   - `lsusb -nn`
   - DMI strings
   - whether sysfs LEDs exist
2. Decide backend type:
   - sysfs backend if present
   - USB backend otherwise
3. Add probe rules + a minimal “smoke path” (brightness/uniform)
4. Validate per-key only after confirming matrix + calibration.

## Testing

- Unit tests for selection and probe logic.
- Optional hardware tests behind `KEYRGB_HW_TESTS=1`.
