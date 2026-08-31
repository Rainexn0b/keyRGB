# Backend Architecture

## Goal

Support additional keyboard-lighting controllers without changing the tray or
GUI UX for every new device.

## Non-goals

- Cross-platform support beyond Linux-first assumptions.
- A privileged daemon/service architecture (for now).
- Auto-generating per-key keymaps (calibration remains the approach).

## Current structure

Backends live under `keyrgb/core/backends/`.

- `base.py`: backend interface + `BackendCapabilities`
- `registry.py`: backend enumeration + selection (`KEYRGB_BACKEND`)
- Canonical inventory, naming rules, and aliases: [`keyrgb/core/backends/README.md`](../../keyrgb/core/backends/README.md)

The current mix includes kernel sysfs (`sysfs/`, `sysfs_mouse/`), ITE USB/hidraw families (`ite8291r3_perkey/`, `ite8910_perkey/`, `ite8291_*`, `ite8258_*`, `ite8295_*`, `ite8297_uniform/`, `ite8233_none_chassis_lightbar_clevo/`), and `asusctl/` for Aura.

Notes:

- Tray and GUI capability checks route through backend selection.
- The device protocol remains intentionally small even when a backend exposes a
	non-keyboard surface such as an auxiliary lightbar.

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
- `color`: supports setting a uniform RGB color
- `hardware_effects`: has built-in firmware effects we can select
- `palette`: supports firmware palette slots / named colors

This should remain additive: new flags can be added, but existing meaning shouldn’t change.

## Backend categories

KeyRGB should stay organized by control path rather than by laptop brand:

1. **USB / hidraw controller** for direct userspace protocols
2. **Sysfs LED class** for kernel-exported keyboard lighting
3. **Platform-specific subprocess or API bridges** when another Linux tool owns the hardware path
4. **Auxiliary uniform devices** that are not the main keyboard but still fit the lighting model

Most currently supported hardware is ITE-derived, but the contract is generic
enough to support other controller families if they can expose the same device
surface.

## Selection philosophy

- Default behavior is `KEYRGB_BACKEND=auto`.
- Auto-selection should pick the best backend based on *actual probe results*.
- Users must be able to force a backend if auto-selection is wrong.
- Experimental and dormant policy should be explicit rather than hidden in
	backend-specific special cases.

## Test philosophy

- Selection logic must be unit-testable without hardware.
- Backend probes should be small functions that can be monkeypatched.
- Hardware smoke tests stay optional (skipped by default).
