# Changelog

## 0.4.0 (2025-12-30)

- Tray: Screen Dim Sync supports `turn off` and `set brightness to` (temporary dim) modes.
- Tray: when the display is powered off via DPMS (e.g. power button), temporary dim mode now turns the keyboard fully off and restores on wake.
- Settings UI: window sizing adjusted so the full panel is visible (screenshot-friendly).
- Docs: updated usage notes and refreshed Settings screenshot.

## 2025-12-29

- Installer: reliably installs the ITE 8291 (048d:600b) udev rule and reloads udev so KeyRGB can access the device without running as root.
- Permissions: improves the ITE 8291 backend error message when device access is denied.
- Internal: refactors Tuxedo Control Center (TCC) power profiles code into a package while preserving the public API.

## 2025-12-30

- Internal: refactors tray code into smaller modules (startup, lighting control, menu sections, polling wrapper) and consolidates UI refresh.
- Tray: syncs keyboard lighting with display dimming; configurable to turn off, dim to a temporary brightness, or disable.
- Tray: in temporary dim mode, turns the keyboard off when the display is powered off (DPMS screen-off), then restores on wake.
- Internal: extracts sysfs AC-power detection into a focused module to reduce platform IO inside `src/core/power.py`.
- Internal: extracts logind (login1) PrepareForSleep monitoring into a focused helper module to reduce DBus parsing/process management inside `src/core/power.py`.
- Internal: extracts the `BatterySaverPolicy` state machine into a focused module to further shrink the `src/core/power.py` hotspot.
- Internal: extracts Settings UI config/state logic into a testable helper module to reduce complexity in the Tk settings window.
- Internal: extracts per-key editor color-map operations into a focused helper module to reduce UI coupling.
- Internal: extracts per-key editor color-apply logic into a focused helper module to reduce UI coupling.
- Tests: adds a small unit test to lock in tray UI refresh behavior.
- Tests: adds unit tests for sysfs power-supply probing.
- Tests: adds a small unit test to lock in logind PrepareForSleep parsing.
- Tests: adds unit tests for Settings UI state loading/apply behavior.
- Tests: adds unit tests for per-key editor color-map operations.
- Tests: adds unit tests for per-key color-apply behavior.
- Effects: slows down and smooths software effects (more interpolation steps and less abrupt transitions) for a more organic feel at low speeds.
- Effects: avoids unintended full-black frames during transitions to reduce brief "keyboard off" blinks when starting/stopping effects or switching to per-key.
- Brightness: avoids persisting transient brightness=0 reads from hardware polling (prevents random brightness resets).
- Per-key: best-effort persists user-mode when applying per-key colors so per-key lighting stays on while typing.
- Docs: documents KDE screen-dim synced lighting behavior.
- Docs: updates tech-debt tracking/hotspots and documents legacy boundaries.
