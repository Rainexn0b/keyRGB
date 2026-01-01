# Battery Saver Policy (Dim on AC unplug)

## Goal

Provide a simple policy for Tongfang laptops: automatically reduce keyboard brightness when AC power is unplugged, and restore it when AC returns.

## Why this is deferred

This is a *policy feature* layered on top of hardware support.

It should be implemented only after:

- backend probing/selection is reliable
- capabilities gating prevents unsupported writes

## Requirements

- Must not require root.
- Must not fight with the user:
  - if the user manually changes brightness while on battery, respect their choice
- Must avoid rapid toggling (debounce)

## Inputs

AC power state options:

- `UPower` via DBus (recommended)
- sysfs power supply state (`/sys/class/power_supply/AC*/online`) as a fallback

## Behavior (minimal)

- On transition AC -> Battery:
  - store current brightness (if > 0)
  - set brightness to a configured lower value (or a fixed safe default)
- On transition Battery -> AC:
  - restore stored brightness (if present)

## Configuration

Prefer minimal config keys (names to be decided when implementing):

- enable/disable battery saver
- target brightness on battery

## Failure handling

- If no backend/device is available, policy should be a no-op.
- If set_brightness fails (device gone), log (throttled) and continue monitoring.

## Related quirk: resume resets controller state

Some ITE-based laptops reportedly resume into a firmware “rainbow cycle” and ignore prior user settings.

Mitigation approach:

- Ensure **restore on resume** is enabled so KeyRGB re-applies the configured effect/brightness after wake.
- If future reports show this isn’t sufficient, add a dedicated “reassert state on resume” step (still best-effort, never blocking startup).

## Test strategy

- Unit tests for state transitions and “manual override” behavior.
- Mock backend/device so no hardware is required.
