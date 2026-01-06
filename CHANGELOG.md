# Changelog

## 0.12.4-rc1 (2026-01-07)

- Refactor: Reduced cyclomatic complexity for radon E-rated hotspots by extracting helpers while preserving public interfaces and test behavior. Targeted items: `buildpython/steps/step_quality.py::code_markers_runner`, `src/core/diagnostics/collectors_backends.py::backend_probe_snapshot`, `src/gui/perkey/overlay/autosync.py::auto_sync_per_key_overlays`, `src/gui/theme/detect.py::detect_system_prefers_dark`.
- Quality: Cyclomatic complexity re-run shows **E-rated blocks: 0**.
- CI: Full build profile is green (Compile, Pytest, Ruff lint/format, Import Validation/Scan, Code Markers, File Size, LOC Check, Type Check).
- Testing: Added/updated unit tests around affected behaviors; all tests pass locally.
- Note: This is a pre-release staged for testing before promoting to the latest stable.

## 0.12.3 (2026-01-06)

- Fix: reduce likelihood of crashes after a USB disconnect by aggressively stopping further USB I/O and marking the device unavailable.
- Fix: ensure per-key disconnect handling marks the device unavailable while holding the device lock to reduce race windows that could lead to libusb crashes.
- Maintenance: centralize USB error classification (device disconnected/busy) to reduce duplicated, inconsistent errno/string checks across tray/effects/GUI (`src/core/utils/exceptions.py`).
- Refactor: extract config property factory helpers into `src/core/config/_props.py` and simplify `src/core/config/config.py` (reduced LOC and clearer property helpers).
- Tests: add unit tests to cover brightness-split behavior, disconnect-safe effect rendering, and software-effects visibility (`src/tests/test_brightness_split_unit.py`, `src/tests/test_effects_render_disconnect_unit.py`, `src/tests/test_software_effects_visibility_unit.py`).
- Fix: correct a syntax/indentation regression in `src/gui/windows/uniform.py` caught by `py_compile`.
- Misc: additional small cleanups and test coverage improvements across tray/pollers/effects/GUI.


## 0.12.2 (2026-01-06)

- Fix: Screen dim/brightness sync now reliably dims the keyboard in per-key mode and detects gradual/stepwise backlight dimming.
- Docs: consolidate end-user usage/reference into `README.md` and update repo layout docs.
- Tests: add extensive non-brittle unit coverage across tray startup/runtime/pollers and core power monitoring/backends.
- Tests: make direct `pytest` invocations reliably import the `src` package by adding the repo root to pytest's `pythonpath`.

## 0.12.1 (beta) (2026-01-05)

- Fix: Installer: restore interactive stable/prerelease AppImage channel prompt for normal installs (keeps `--update-appimage` non-interactive and preserves saved selection).
- Fix: GUI: increase Reactive Typing Color window height to avoid clipping the bottom controls.
- Fix: Tray: avoid brief hardware/uniform color flashes when adjusting effect brightness in software mode (update engine brightness in-place without issuing a hardware brightness write or restarting software effects).
- Tests: updated unit tests to reflect the new brightness behavior.

## 0.12.0 (beta) (2026-01-05)

- GUI: refactor theme logic into a dedicated `src/gui/theme/` package while keeping the public import path stable (`from src.gui.theme import apply_clam_theme`).
- GUI: add a dedicated reactive typing color UI (`keyrgb-reactive-color`) to set a manual highlight color for `reactive_fade` / `reactive_ripple`.
- Tray: config polling can apply reactive manual-color changes live without restarting the running effect.
- GUI: consolidate GUI modules into clearer packages (`src/gui/windows/`, `src/gui/utils/`, `src/gui/reference/`, `src/gui/tcc/`) and remove remaining legacy GUI shims.
- GUI: move calibrator launcher into `src/gui/calibrator/launch.py` and keep the `keyrgb-calibrate` entrypoint working.
- Build/AppImage: add `KEYRGB_APPIMAGE_STAGING_ONLY` and `KEYRGB_APPIMAGE_SKIP_DEPS` to regenerate the AppDir when dependency builds are unavailable, and refresh the staged AppDir to match the new module layout.
- Docs: update README + usage docs to reflect current entrypoints and GUI locations.
- Tests: add/update unit tests covering the reactive typing color config + related tray/controller behaviors.

## 0.11.5 (2026-01-05)

- Profiles/Per-key editor: add built-in `dark` profile preset (all keys off) to better showcase reactive typing effects.
- Profiles/Per-key editor: change built-in `default` profile colors to all-white.
- Diagnostics: when running from a source checkout, report the repo version from `pyproject.toml` (and include the installed dist version separately).

## 0.11.4 (2026-01-05)

- Installer: add `--update-appimage` for non-interactive AppImage updates (reuses the last saved release channel selection).

## 0.11.3 (2026-01-05)

- Fix: Version panel no longer requires Python 3.11+ `tomllib` and now reads `pyproject.toml` with a small, dependency-free parser so Import Scan works on older Python runtimes (fixes CI import-scan failure).

## 0.11.2 (2026-01-05)

- Settings: Version panel shows the source checkout version in dev mode (avoids stale pip-installed version confusion).
- UI/Docs: clarify “Screen dim/brightness sync” wording and behavior (e.g. KDE brightness slider).
- Installer: kernel driver install respects `--no-system-deps` / `KEYRGB_SKIP_SYSTEM_DEPS=1` and uses shared package-manager helpers.
- README: Quickstart cleanup, with one-line interactive install/uninstall commands that fetch the latest scripts (no clone).
- Docs: reorganize and refresh architecture/maintainer docs (CI/build logs + maintainer workflows).

## 0.11.1 (2026-01-05)

- Installer: improved AppImage download UX (shows a progress bar in interactive shells).
- Installer: avoid Python traceback on GitHub API failures; now fails quietly and falls back to the latest stable release URL.
- Installer: add navigation headers and VS Code folding regions to make `install.sh` easier to navigate.
- Installer: small messaging tweaks and friendly prompts (Star the project / open an issue if you found a problem).

## 0.11.0 (2026-01-05)

- Backends: renamed the ITE USB backend package to `ite8291r3` (protocol-scoped) and removed the legacy `ite` shim.
- Backends: expanded safe USB ID handling (allowlist + explicit denylist for known other protocol families, including `048d:c966`).
- Backends: added a dormant `ite8297` backend scaffold (disabled by default; requires confirmed IDs + implementation).
- Power/Tray: fixes resume behavior where some keyboards come back dark until the user clicks “Turn On”.
- Permissions: udev uaccess rule covers common supported ITE 8291r3 USB IDs.
- Docs: added a contributor workflow for safely verifying a new VID:PID before submitting a PR.

## 0.10.2 (2026-01-04)

- Installer: improve AppImage download reliability by downloading to a temporary file, adding clearer diagnostics on write failures, and falling back from `curl` → `wget` → `python3` when needed.
- Installer: better diagnostics for local write issues (disk full, permission denied) when AppImage download fails.
- Uninstall: preserve `kernel-drivers-installed-by-keyrgb` marker when removals were skipped or failed so follow-up uninstalls can retry only remaining packages.
- Docs: minor README/CHANGELOG clarifications.

## 0.10.1 (2026-01-04)

- Installer: expands best-effort system dependency installation beyond Fedora/Nobara via common package managers (dnf/apt/pacman/zypper/apk).
- Installer: adds `--no-system-deps` / `KEYRGB_SKIP_SYSTEM_DEPS=1` to skip system package installation (useful for minimal/immutable setups).
- Docs: updates README to clarify best-effort cross-distro installer support and the new skip-deps option.

## 0.10.0 (2026-01-04)

- Installer: adds an optional kernel driver installation step to `install.sh` to help install `tuxedo-drivers` / `tuxedo-keyboard` and `clevo-xsm-wmi` packages (best-effort) for safer, kernel-level keyboard control.
- Backends: Sysfs backend is preferred (higher priority) over the ITE USB userspace driver when kernel interfaces are available, avoiding USB-level conflicts and improving reliability.
- Sysfs improvements: expanded detection for Clevo/Tuxedo/System76 naming patterns and added System76 multi-zone color file support (`color_left`, `color_center`, `color_right`, `color_extra`).
- Tray: device header now shows friendly names ("Kernel Driver" vs "ITE 8291 (USB)") and reports LED names or USB VID:PID for clearer diagnostics.
- Docs: README, usage, and architecture docs updated to document multi-backend priority, kernel driver support, and installer options.
- Tests: added unit tests for sysfs detection, System76 color zones, and tray display formatting.

- UI: completes dark-theme styling for Settings panels to match the color editor (removes bright/white blocks) and improves cursor/state affordances in overlay editors.
- Tray: fixes HW/SW mode switching so selecting Hardware Color reliably unlocks hardware effects and locks software effects.
- Performance: significantly speeds up uniform and per-key UI startup by caching the color wheel as a single raster image and deferring initial render.
- Maintenance: extracts shared helpers to improve maintainability and reduce duplication (`src/gui/tk_async.py`, `src/gui/key_draw_style.py`, `src/gui/perkey/color_utils.py`), consolidates geometry calculations (`calc_centered_drawn_bbox`/transform helpers), and centralizes overlay hit-testing/geometry in the per-key canvas to simplify the overlay drag controller.
- Maintenance: refactors per-key canvas and calibrator geometry to ensure consistent rounding, transform creation, and backdrop centering; small pure helper extraction across the per-key modules reduced duplicated logic.
- Testing/Quality: Ruff configuration and repeated pytest gating applied during refactors; all tests pass after these changes.
- Release prep: finalizes changes intended for the `0.10.0` update (see below for tagging/commit).


## 0.9.4 (2026-01-04)

- UI: completes dark-theme styling for common ttk widgets in Settings (removes bright/white default blocks).
- Tray: fixes HW/SW mode switching so selecting Hardware Color reliably unlocks HW effects and locks SW effects.
- Performance: significantly speeds up uniform/per-key GUI startup by caching the color wheel as a single image and deferring heavy rendering.
- Maintenance: removes legacy effect aliases/normalization (`reactive_snake`/`reactive_rainbow`, old per-key names) and prunes unused compatibility shims/fallbacks.
- Docs: updates commands/effects notes to match current supported effect set.

## 0.9.3 (2026-01-04)

- Tray: tight HW vs SW mode lockdown (incompatible menu items are greyed out), and software effects can run without forcing a profile load (“loose” uniform color state).
- Per-key editor: adds a “New profile” workflow and improves profile ergonomics.
- Maintenance: centralizes effect catalog/labels and effect-name normalization to reduce drift between engine and tray; general cleanup + lint/format.
- Docs: adds a dedicated commands doc and repo layout notes; refreshes screenshots.

## 0.9.2 (2026-01-03)

- Tray: refreshed menu layout and labeling for a more native desktop feel (emoji-free, clearer section ordering).
- Per-key editor: Profiles are always visible and the bottom panel space is split evenly (overlay editor appears without window resizing).
- UI: improves dark-theme styling for per-key editor panels and common input widgets.

## 0.9.1 (2026-01-03)

- Brightness: tray brightness selection now persists cleanly across restarts (brightness is normalized to the 0..50 step grid the tray exposes).
- Brightness: hardware polling no longer overwrites `config.json` brightness values (prevents “no selection”/scale mismatch issues).
- Power: clarifies and stabilizes brightness semantics between baseline (AC/battery policies) vs temporary overrides (tray + screen-dim sync).
- Screen Dim Sync: temporary dim-to-brightness no longer clobbers user/baseline settings; restore behavior is more consistent.
- Diagnostics: adds INFO-level `EVENT ...` logs for menu actions, config apply decisions, idle/power actions, and hardware brightness changes.
- Maintenance: groups config modules under `src/core/config/` with backward-compatible shims for older import paths.

## 0.9.0 (2026-01-03)

- Reworked software effects engine.
- Effects: replaces/expands software effect suite with new animations (Rainbow Wave/Swirl, Spectrum Cycle, Color Cycle, Chase, Twinkle, Strobe).
- Effects: adds reactive typing effects (Reactive Fade/Ripple/Rainbow/Snake) with calibrated per-profile key mapping.
- Effects: adjusts speed mapping so speed=10 is significantly faster.
- Permissions: adds an optional udev `uaccess` rule install path to allow safe keypress capture via evdev (without adding the user to the `input` group).
- Tray: updates effect menus to include the new software/reactive effects and reduces fragile/dynamic tray icon updates for SW effects.
- Fixed a bug where the wrong color mode would be selected when an effect was activated

## 0.8.0 (2026-01-02)

- Power: adds lightweight “Power Mode” (Extreme Saver/Balanced/Performance) with a tray toggle; uses cpufreq sysfs and best-effort boost handling.
- Power: optional passwordless switching via a small pkexec helper + polkit rule installed by `install.sh`.
- Tray: adds “🔋 Power Mode” menu; renames TCC menu to “Power Profiles (TCC)” and avoids showing both power control systems at once.
- Installer: adds interactive install mode selection (AppImage / clone / repo editable) and defaults to newest stable AppImage unless `--prerelease`.
- Installer/Uninstaller: optional Tuxedo Control Center install/remove via `dnf` when TCC integration is selected.
- Diagnostics: adds a system power-mode snapshot in `keyrgb-diagnostics`.
- Safety: detects some ITE “Fusion 2” devices (048d:8297/5702) as detected-but-unsupported (fail-closed).
- Devices: improves sysfs LED backend candidate selection reliability.

## 0.7.9 (2026-01-02)

- Tray/AppImage: prefer the AppIndicator backend when available and bundle the needed `gi` + GI typelibs in the AppImage (fixes “square/blocky” and non-clickable tray icon behavior seen on some desktops with the GitHub-built AppImage).

## 0.7.8 (2026-01-02)

- Tray/AppImage: fixes a startup crash on some systems where a non-PyGObject `gi` module is present; KeyRGB now falls back to the Xorg tray backend instead of failing.

## 0.7.7 (2026-01-02)

- Desktop integration: starting KeyRGB from the app menu works more reliably (desktop launcher `Exec=` path fix).
- Per-key editor: “Open Color Editor…” launches reliably (fixes subprocess working directory).
- Assets: backdrop/keyboard image lookup no longer depends on the current working directory; the default deck image is bundled into the AppImage.

## 0.7.1 (2026-01-02)

- Distribution: releases now ship a `keyrgb-x86_64.AppImage` asset.
- Installer: `./install.sh` defaults to AppImage mode and installs a single binary to `~/.local/bin/keyrgb`.
- Installer: `--pip` mode remains available for development (editable install via `pip --user -e .`).
- Packaging: RPM packaging support has been removed.
- Permissions: udev rule is now tracked at `system/udev/99-ite8291-wootbook.rules` and is installed by `install.sh`.

- Build/CI: `buildpython` gained an AppImage build step and CI uploads the AppImage as an artifact.
- Releases: tags now trigger a workflow that builds and attaches the AppImage to the GitHub Release.

- Safety/testing: tests are hardened to avoid touching real hardware by default; hardware tests remain opt-in.
- Maintenance: major internal refactor and shim removal to standardize canonical imports and tray entrypoints.

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
