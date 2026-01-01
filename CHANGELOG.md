# Changelog

## 0.6.0 (2026-01-01)

- Per-key editor: adds a sample tool (pick a key color, then paint other keys).
- Per-key editor: status/messages are clearer and wrap better in the UI.
- Color wheel: adds manual RGB input (precise values) and optional compact label mode.
- Tray: adds clearer status UI (device header + “Active:” mode indicator).
- Theme: optional Tk scaling override via `KEYRGB_TK_SCALING` (useful for DPI/layout quirks).

- Devices: improves sysfs LED backend detection and adds best-effort multi-color support via `multi_intensity` / `color`.
- Devices: expands ITE USB probing fallbacks (additional `0x048d:*` product IDs).

- Maintainability: reorganizes tray modules by purpose (controllers, pollers, startup, UI, integrations) while keeping import compatibility.
- Maintainability: reorganizes core helpers by purpose (monitoring, profile, power policies, resources/runtime helpers) while keeping import compatibility.

## 0.5.1 (2026-01-01)

- Per-key editor: status bar uses full-width wrapping; clearer, more actionable error messages.
- Per-key editor: adds a sample tool (pick a key color, then paint other keys).
- Color wheel: adds manual RGB input and optional compact label mode.
- Tray: adds a keyboard/device status header and an “Active:” mode indicator.
- Theme: optional Tk scaling override via `KEYRGB_TK_SCALING` (for DPI/layout testing).

## 0.4.0 (2025-12-30)

This release note covers changes since `v0.2.1` (GitHub Releases were behind the tags).

- Tray: adds Screen Dim Sync (turn off, temporary dim-to-brightness, or disabled).
- Tray: when the display powers off via DPMS (e.g. power button), temporary dim mode now turns the keyboard fully off and restores on wake.
- Settings: adds AC/battery lighting controls.
- Settings: adds Diagnostics runner and expands diagnostics JSON (USB device holders/process info, power/config snapshots).
- Settings: improves layout/scrolling and adjusts window sizing so the full panel is visible (screenshot-friendly).
- Per-key: reduces random brightness resets and best-effort preserves user-mode so per-key lighting stays active while typing.
- Effects: smoother timing/transition behavior; avoids brief full-black frames (“keyboard blink off”).
- Installer: hardens udev rule installation/reload so KeyRGB can access the device without running as root.
- Packaging: adds `uninstall.sh` for `install.sh` installs; updates local RPM/SRPM scripts/instructions.
- Internal: refactors tray modules and power management helpers (logind PrepareForSleep, sysfs power-supply, BatterySaverPolicy, TCC profiles) and adds/expands unit tests.

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
