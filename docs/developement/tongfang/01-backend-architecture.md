# Backend Architecture (Tongfang-only)

## Goal

Support additional Tongfang laptop keyboard controllers without changing the tray/GUI UX for every new device.

## Non-goals

- Supporting non-Tongfang devices.
- A privileged daemon/service architecture (for now).
- Auto-generating per-key keymaps (calibration remains the approach).

## Current structure

Backends live under `src/core/backends/`.

- `base.py`: backend interface + `BackendCapabilities`
- `registry.py`: backend enumeration + selection (`KEYRGB_BACKEND`)
- `ite8291r3.py`: first backend adapter

Compatibility shims:

- Tray dimensions route through backend selection.
- Legacy ITE imports are preserved via a wrapper module.

## Backend contract (stable surface)

A backend provides:

- `name`: stable identifier for env selection
- `priority`: ordering when auto-selecting
- `is_available()`: *fast* detection/probe (should not spam logs)
- `capabilities()`: feature flags
- `get_device()`: returns a device instance implementing the minimal keyboard protocol
- `dimensions()`: matrix dimensions `(rows, cols)` if per-key is supported
- `effects()` / `colors()`: dictionaries used by existing menu/effects code

## Capabilities (current)

`BackendCapabilities` currently includes:

- `per_key`: supports `set_key_colors` and a real matrix
- `hardware_effects`: has built-in firmware effects we can select
- `palette`: supports firmware palette slots / named colors

This should remain additive: new flags can be added, but existing meaning shouldn’t change.

## Tongfang-only backend categories

We expect Tongfang models to cluster into a few control paths:

1. **USB controller** (like current ITE 8291/8291r3)
2. **Sysfs LED class** (e.g. `/sys/class/leds/*kbd*`)
3. **Platform driver hooks** (ACPI/WMI/EC exposed via sysfs)

Backends should be categorized by control path, not by chassis brand name.

## Selection philosophy

- Default behavior is `KEYRGB_BACKEND=auto`.
- Auto-selection should pick the best backend based on *actual probe results*.
- Users must be able to force a backend if auto-selection is wrong.

## Test philosophy

- Selection logic must be unit-testable without hardware.
- Backend probes should be small functions that can be monkeypatched.
- Hardware smoke tests stay optional (skipped by default).
