# Backend Architecture

## Goal

Support additional keyboard-lighting controllers without changing the tray or
GUI UX for every new device.

## Non-goals

- Cross-platform support beyond Linux-first assumptions.
- A privileged daemon/service architecture (for now).
- Auto-generating per-key keymaps (calibration remains the approach).

## Current structure

Backends live under `src/core/backends/`.

- `base.py`: backend interface + `BackendCapabilities`
- `registry.py`: backend enumeration + selection (`KEYRGB_BACKEND`)
- `sysfs/`: kernel / LED-class backend
- `ite8291r3/`: ITE 8291r3 USB backend (protocol-scoped package)
- `ite8910/`: reverse-engineered hidraw backend with per-key support
- `ite8297/`: experimental hidraw backend for uniform RGB paths
- `ite8233/`: experimental auxiliary lightbar backend
- `asusctl/`: subprocess-backed Aura integration

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
