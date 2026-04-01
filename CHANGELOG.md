# Changelog

## unreleased

## 0.19.2 (2026-04-01)

- Backends/Lightbar: Promote `ite8233` for the confirmed secondary `0x048d:0x7001` Tongfang/MECHREVO HID device from dormant scaffold to an opt-in experimental backend, using the upstream-backed single-zone lightbar path for uniform color, brightness, and off via `hidraw`.
- Docs/Backends: Add a backend research note for the suspected ITE 8233 auxiliary lightbar path, including current evidence, unknowns, required dumps, and the promotion criteria for moving from dormant to experimental.
- Docs/Workflow: Add a staged diagnostics and backend-discovery roadmap covering the tray-first support surface, safe discovery scanners, and the planned export flow for new backend reports.
- GUI/Settings: Remove the Diagnostics and Keyboard Layout sections from Settings so support flows can move to the tray and physical layout stays owned by the per-key editor setup flow.
- Tray/Support: Add first-pass tray-first Debug and Detect New Backends entries, plus a dedicated Support Tools window that can run the existing full diagnostics report and a new safe device-discovery scan without going through Settings.
- Diagnostics/Discovery: Add a read-only device discovery snapshot that cross-references backend probes, USB IDs, USB sysfs details, and hidraw enumeration so dormant, experimental-disabled, supported, and unrecognized ITE-class devices can be surfaced explicitly.
- Diagnostics/Hidraw: Capture hidraw report descriptors safely with read-only ioctls when access is available, and include descriptor sizes in the backend-discovery output so new controller reports carry more actionable evidence by default.
- GUI/Support: Add save-to-file export for diagnostics and discovery output, plus a combined support-bundle export for issue attachments.
- Diagnostics/Support: Add issue-template-aware support actions and generated issue drafts so discovery output, saved bundles, and tray support flows point users at the right GitHub form with more complete first-round evidence.
- GUI/Support: Add an in-window support-issue preview with the recommended template and issue URL, so users can review the generated draft before copying, saving, or opening the GitHub form.
- Diagnostics/Support: Include optional deeper-evidence commands like `lsusb -v` and `usbhid-dump -e descriptor` in unsupported-device guidance when the read-only scan still lacks enough protocol evidence.
- Tray/Support: Collapse the tray's flat diagnostics and backend-discovery entries into a single `Support Tools` submenu to keep the top-level menu shorter while preserving the same support actions.
- Tray/Support: Simplify the tray launch path further to a single `Support Tools…` entry, since both support flows now live in the same window.
- GUI/Support: Clarify export button labels so diagnostics JSON, discovery JSON, and the combined support bundle are easier to distinguish.
- GUI/Support: Add a guided “Collect missing evidence…” flow for unsupported devices, including optional privileged `usbhid-dump` capture and bundle persistence so issue-5-style reports can gather deeper USB/HID data from the UI.
- Diagnostics/Support: Extend support bundles and hardware-support issue drafts/templates with supplemental evidence capture results when the initial scans still lack the required protocol data.
- GUI/Per-key Editor: Add a profile-backed conditional `Lightbar` placement panel beneath `Overlay alignment`, with a resizable preview, transform controls, and a matching chassis overlay rendered on the main editor canvas when a secondary lightbar device is discovered.
- Tray/UI: Make the top tray device status rows selectable device contexts so the menu body can switch between keyboard controls and secondary-device surfaces, instead of forcing future lightbar controls into the keyboard menu.
- Tray/UI: Persist the selected tray device context in config so the tray reopens on the last chosen device, while still falling back to `Keyboard` if that saved secondary device is no longer present.
- Tray/UI: Split non-keyboard device-context rendering into dedicated tray menu section builders so future device types can plug in their own context surfaces without growing more branches inside the main keyboard menu builder.
- Tray/Lightbar: Replace the lightbar selector placeholder surface with real `Color…`, `Brightness`, and `Turn Off` actions, backed by independent lightbar color/brightness config state and a target-aware uniform color window.
- Effects/Software: Introduce a real software-effect target policy (`Keyboard Only` vs `All Compatible Devices`) so looped software and reactive effects can mirror their uniformized output to compatible auxiliary devices like the experimental `ite8233` lightbar without folding those devices into keyboard-only engine logic.

## 0.19.1 (2026-04-01)

- GUI/Reactive Color: Fix the Reactive Typing color window crash when opening it with the shared ColorWheel brightness slider hidden; programmatic brightness sync now works without requiring the wheel's internal slider state.
- GUI/Calibrator: Make the keymap calibrator load layout-specific keymap and overlay defaults using the active Keyboard Setup physical layout, so ISO and other variants carry through consistently when no custom profile files exist yet.
- GUI/Per-key Editor: Reorder the main setup actions into the intended workflow (`1. Keyboard Setup`, `2. Keymap Calibrator`, `3. Overlay Alignment`), remove the redundant manual keymap-reload button from the main surface, and rely on in-context reset actions for each setup stage instead.
- Effects/Software: Fix per-key software effects randomly bouncing between colors instead of animating smoothly on `ite8291r3`: re-assert user mode (`SET_EFFECT`) before every `set_key_colors` call so the controller cannot revert to its saved hardware effect between frames.
- Effects/Software: Fix choppy high-speed appearance on rainbow swirl, rainbow wave, spectrum cycle, and color cycle by reverting those effects to a constant per-frame step instead of elapsed wall-clock time; USB write-time jitter was being amplified by the pace multiplier (up to ×10 at max speed) and causing visible color steps.
- Effects/Software: Eliminate the brief dark-dip flicker when switching between software effects by skipping the fade-in animation when the previous effect was also a software effect; the keyboard stays in user mode between effects so the new effect's first frame is seamless.
- Effects/Software: Save and restore speed independently per software effect so each animation remembers its own last-used speed; changing speed no longer requires restarting the effect loop, and switching between effects preserves each effect's individual pace.
- Effects/Reactive: Fix speed changes having no visible effect on reactive typing animations (`reactive_fade`, `reactive_ripple`): `pace()` is now re-evaluated each frame so changing speed via the tray menu is reflected immediately in pulse lifetime and spawn rate without restarting the effect.
- Build/Type Checking: Fix pre-existing mypy errors in `config_polling_internal/core.py` (cast ambiguous `tuple(color)` results) and `buildpython/core/summary.py` (variable name shadowing and redefinition); `src/core`, `src/tray`, and `buildpython` now pass mypy cleanly.


## 0.19.0 (2026-03-31)

- GUI/Keyboard Setup: Split keyboard setup from lighting profiles so layout selection, layout reset, and optional-key setup now live in a dedicated flow while lighting profile controls stay visible in the per-key editor.
- GUI/Layout Support: Add a shared physical keyboard layout catalog with `auto`, `ansi`, `iso`, `ks`, `abnt`, and `jis` variants, plus better auto-detection, layout-specific starter defaults, optional-key handling, and more accurate ISO/ABNT/JIS overlay geometry.
- Effects/Lighting Reliability: Harden reactive typing and software-render restarts by ignoring non-keyboard event devices, cleaning up input readers correctly, preventing stale workers from overwriting newer runs, and reducing visible per-key flashing on `ite8910`.
- Backends/Diagnostics: Tighten backend probing and sysfs detection, improve diagnostics output, and make experimental-backend status and tray capability reporting clearer.
- Installer/Desktop Integration: Keep `--update-appimage` user-local without re-running udev setup, and refresh desktop/icon caches more reliably so updated icons and desktop entries take effect after installs and updates.
- Build/Quality: Add architecture and debt reporting to `buildpython`, improve coverage reporting, move the test suite out of the shipped app package/AppImage path, and substantially increase automated coverage across core, GUI, and tray workflows.
- Docs/Maintenance: Reorganize contributor docs, add active tech-debt tracking, and document the updated build, release, and reactive-brightness workflows more clearly.


## 0.18.6 (2026-03-29)

- Effects/Runtime Boundaries: Inject the selected backend into `EffectsEngine` device acquisition and hardware-effect dispatch, make direct engine hardware starts validate against backend-exposed effects instead of the legacy global adapter, and keep software effects authoritative unless a hardware selection is explicitly namespaced.
- Effects/Legacy Cleanup: Replace the remaining software/reactive matrix-size dependency on `src/core/effects/ite_backend.py` with a backend-agnostic `src/core/effects/matrix_layout.py` module, then remove the obsolete shim.
- Docs/Workflow: Add an experimental backend confirmation issue template for promotion requests, and clarify in the README that hardware effect names are backend-specific, `hw:` preserves hardware/software name collisions, and `--update-appimage` also refreshes desktop integration and udev setup.
- GUI/Installer: Prefer the SVG app logo for Tk window icons when optional rasterization support is available, keep PNG fallback behavior intact, and install/remove the scalable icon alongside the existing desktop PNG asset.
- Tests: Add focused regressions for backend-injected engine hardware dispatch, backend-aware direct effect validation, hardware/software collision handling, tray startup wiring of the selected backend into the effects engine, and SVG/PNG window-icon cache and fallback behavior.

## 0.18.5 (2026-03-29)

- Tray/Backend Awareness: Resolve tray effect selection, startup state, config polling, menu labels, and icon behavior against the detected backend so hardware-effect menus reflect real backend capabilities and hardware/software name collisions are handled explicitly.
- Tray/Icon/Assets: Switch the tray icon renderer to the new SVG mask asset, tighten animated icon polling to truly animated states, refresh the bundled app/tray branding assets, and update packaging/install paths to use the new squircle app icon.
- Docs/Project Organization: Reorganize development docs into `docs/developement/backends/`, `docs/developement/commits/`, `docs/developement/archived/`, and `docs/venv/`, remove the stale flat dev-doc copies, and update internal references to the new structure.
- Tests: Add focused tray regressions covering backend-aware effect selection, menu capability detection, config normalization, startup icon wiring, animated icon polling, and the updated tray icon cache/visual behavior.

## 0.18.4 (2026-03-29)

- Backends/ITE8910: Fix the remaining issue #4 behavior on `ite8910` by aligning logical `(row, col)` writes with KeyRGB's bottom-up saved-keymap convention, stopping per-frame reset/black clears in software/reactive incremental updates, and preserving the backend's direct firmware speed scale.
- GUI/Calibrator/Profiles: Use backend-provided matrix dimensions in the calibrator and per-key editor paths, and sanitize out-of-range keymap/per-key color cells on load so older 6x21 profile state cannot bleed into the 6x20 `ite8910` path.
- GUI/ISO: Extend the built-in reference keyboard overlay with the ISO-only key beside left shift and map `KEY_102ND` into the reactive/keymap identifier model so ISO users can calibrate and use the extra key.
- Backends/Shared Defaults: Replace scattered hardcoded fallback matrix sizes and string-based hardware-speed detection with shared reference-matrix defaults and explicit backend/device speed-policy metadata.
- Tests/Docs: Add focused regression coverage for `ite8910` translation and speed-policy metadata, profile sanitization, calibrator dimension wiring, reference defaults/layout invariants, and document the issue #4 investigation in `docs/bug-reports/issue-4.md`.

## 0.18.3 (2026-03-29)

- Backends/ITE8910: Rewrite the `ite8910` HID protocol around the published reverse-engineered 6-byte `0xCC` feature-report spec, including corrected command builders, mode sequencing, and slot handling for reliable firmware control.
- Backends/ITE8910: Add full end-to-end firmware effect support for direction and custom color control, including 8-direction wave handling, 4-direction snake handling, corrected random-color slot usage, and tracked mode/brightness updates so unchanged writes are skipped.
- Backends/ITE8910: Promote `ite8910` from experimental to validated after hardware-backed verification, keeping it eligible by default during backend selection.
- Tray/Effects: Route firmware effect direction through the tray lighting controller and hardware payload pipeline so UI-selected direction and color settings reach the validated `ite8910` backend correctly.
- Config: Add persistent direction-aware configuration defaults and state wiring required for the expanded `ite8910` firmware effect controls.
- Tests/Docs: Expand protocol notes and translation coverage to lock in the corrected packet shapes, direction-slot mappings, and firmware behavior documented by the reverse-engineering notes; README now reflects `ite8910` as validated hardware support.

## 0.18.2 (2026-03-29)

- Backends/ITE8910: Correct the experimental `ite8910` HID framing to the documented 6-byte `0xCC` feature reports, switch the backend to the full reverse-engineered 6x20 LED matrix, and clear the deck before per-key rewrites so stale LEDs do not survive sparse or dynamic updates.
- Backends/Policy: Keep the `validated` / `experimental` / `dormant` stability model, but add an experimental evidence tag so diagnostics can distinguish speculative backends from public reverse-engineering based ones; the `ite8910` backend is now tagged `reverse_engineered`.
- Backends/Attribution: Add code and README attribution for the public ITE 8910 reverse-engineering work by Valentin Lobstein (`chocapikk`, Reddit `Greedy-Ad232`) that informed the corrected experimental backend.
- Tray/Settings: Surface experimental backend evidence with clearer user-facing wording (`research-backed` vs `speculative`) in Settings copy, hardware hints, and the selected-backend tray status line.
- Backends/ITE8297: Promote `ite8297` from dormant scaffold to an opt-in experimental `hidraw` backend for the confirmed `0x048d:0x8297` path, using the public 64-byte uniform-color HID report shape and conservative non-per-key capabilities.
- Sysfs/ITE8297: Detect TUXEDO-style `ite_8297:1/2/3` kernel LED channel triplets and drive them as a single uniform RGB device instead of missing them or treating them as independent zones.

## 0.18.1 (2026-03-28)

- Reactive/Per-key: Restore reactive typing brightness control on per-key hardware by scaling pulse intensity from the reactive slider itself instead of saturating at the steady-state hardware brightness.
- Profiles: Lower the built-in `dim` profile baseline from 15 to 10 and migrate stale built-in dim/light brightness states accordingly.
- Tray/Icon: Make the `K` cutout follow the active per-key profile color for reactive effects when manual reactive color is disabled, and darken the outer logo squarcle to grey for better white-profile contrast.
- Tray/Icon/Memory: Cache rendered solid tray icon images so steady-state icon refreshes can reuse the same PIL image when the visible color has not changed.
- Tray/Icon/Memory: Avoid redundant per-key tray-icon map copies and skip unnecessary full-grid rebuilds when deciding whether per-key base state is actually non-uniform.
- Tray/Icon/Memory: Cache rendered rainbow tray icon frames by phase and brightness scale so animated tray effects stop rebuilding equivalent gradient images across polling ticks.
- Tray/Memory: Reuse the existing config per-key mapping when handing software-mode state to the effects engine, avoiding extra full-map clones during effect starts, restores, and similar tray-driven mode changes.
- Tray/Memory: Reuse the configured per-key map on config-apply paths when it is already empty or full, allocating a new map only when sparse fills are actually required.
- GUI/Memory: Reuse cached resized keyboard backdrops in the per-key editor and calibrator so routine canvas redraws stop reallocating a full deck image every time.
- GUI/Memory: Share cached profile backdrop source images across overlay-based windows so the per-key editor and calibrator stop decoding separate in-memory copies of the same deck file.
- GUI/Memory: Cache the resized window-icon source image so opening multiple Tk windows in one session stops decoding and resizing the same logo repeatedly.
- Reactive/Memory: Reuse the reactive renderer's backdrop base-map buffers so per-key reactive loops stop allocating fresh backdrop dicts every frame.
- Software/Memory: Reuse frame-map buffers in common software-effect loops so breathing, strobe, chase fallback, and uniform color-cycle effects stop rebuilding full keyboard dicts every tick.
- Reactive/Memory: Age pulse lists and reuse fade/ripple overlay and frame-map buffers in place so reactive loops stop rebuilding short-lived collections every frame.
- Buildpython: Add a runtime copy-hotspot scanner to the code-hygiene step so tray/effects regressions that reintroduce avoidable hot-path clones are surfaced during local quality runs.

## 0.18.0 (2026-03-28)

- Power/Reactive: Fix full-brightness flash on wake from screen-dim-off: reset the reactive render's per-frame brightness guard on `stop()` so the render loop ramps from dark instead of jumping to the last pre-stop brightness on the first frame.
- Power/Reactive: Use lightweight `SET_BRIGHTNESS` for frame-to-frame brightness changes during reactive rendering instead of full mode reinit (`SET_EFFECT`), eliminating visible LED strobe during dim↔restore ramps.
- Power/Reactive: Prevent double `SET_EFFECT` on restore-from-idle by recording the mode brightness after the startup per-key fade so the reactive render's first frame skips a redundant mode reinit.
- Power/Reactive: Temporarily cap `reactive_brightness` and `per_key_brightness` to match the fade-in start value during restore, so `_resolve_brightness()` tracks the intended ramp instead of jumping to the stale profile value on the first frame.
- Power/Transitions: Retune idle and power soft-off / soft-on timings so screen dim, wake, and related restore paths fade more deliberately instead of snapping between states.
- Power/Reactive: Add a render-time transition for reactive temp-dim and restore so the dim-profile path visibly fades between brightness levels instead of jumping to the target in a few guard-limited frames.
- Power/Reactive: Skip the cosmetic per-key fade when starting at brightness ≤ 1 (wake-from-idle), letting the reactive render's first frame initialise user mode atomically instead of sending a separate `SET_EFFECT` that flashes on some firmware.
- Power/Reactive: Use `apply_to_hardware=False` for the brightness fade-in with reactive effects so the render loop is the sole hardware brightness writer, preventing stutter from two threads fighting over `SET_BRIGHTNESS`.
- Power/Reactive: Initialise user mode at brightness 0 (invisible) before starting the render thread on wake, then send per-key data before each `SET_BRIGHTNESS` update, so the brightness ramp never briefly illuminates stale frame data.
- Power/Tray: Fix `_start_current_effect` to accept keyword arguments (`brightness_override`, `fade_in`, `fade_in_duration_s`) so the restore-from-idle path actually uses the fade-in ramp instead of silently falling back to an instant full-brightness start.
- Power/Reactive: Stop per-key reactive typing from lifting whole-keyboard hardware brightness on each keypress; keep pulse-time brightness lifts restricted to uniform-only backends so local ripples stay visible without keyboard-wide flicker.
- Tests/Docs: Add backend-split reactive renderer regressions and document the brightness invariants that protect dim, restore, startup, and per-key reactive behavior.

## 0.17.3 (2026-03-26)

- Installer/AppImage: Install a small launcher wrapper at `~/.local/bin/keyrgb` and store the real AppImage as `~/.local/bin/keyrgb.AppImage`, so fresh systems without `libfuse.so.2` automatically fall back to `--appimage-extract-and-run` instead of failing to launch.
- Installer: Mark Arch / CachyOS / EndeavourOS / Manjaro as a tested distro path (promoted from experimental) and document the `fuse2` install step.

## 0.17.2 (2026-03-09)

- Tray/Icon: Make the tray-logo `K` cutout follow active effect visuals so dynamic effects keep the icon in sync with live keyboard behavior.
- Tray/Icon: For reactive typing, respect the manual-effect-color toggle so disabling it makes the `K` cutout mirror base color/per-key state instead of a stale reactive override.
- Tray/Icon: Align startup icon rendering with the same visual-selection pipeline used during runtime refreshes so first paint and steady-state behavior match.
- Tests: Add and update tray icon regressions for reactive color-toggle behavior, reactive base-mosaic fallback, and startup icon construction.

## 0.17.1 (2026-03-09)

- Power/Reactive: Propagate temporary dim state onto the effects engine itself so reactive brightness resolution consistently sees dim-mode state instead of relying on tray-only bookkeeping.
- Power/Reactive: Remove lock-held reactive brightness fades during dim/restore and switch those transitions to atomic state updates so the 60 FPS render loop no longer stalls for the full fade window.
- Power/Reactive: Add a per-frame reactive brightness stability guard to clamp sudden hardware-brightness jumps and smooth dim↔restore ramps without reintroducing stale-brightness flashes.
- Tests: Add focused regression coverage for brightness-guard convergence, engine dim-state propagation, and reactive dim/restore ordering to lock in the no-flicker behavior.

## 0.17.0 (2026-03-09)

- Backends: Add a dedicated `ite8910` translation of the public ITE 829x (`0x048d:0x8910`) C protocol, including exact packet-builder tests and LED-range coverage.
- Backends: Add backend stability classes (`validated`, `experimental`, `dormant`), make `ite8910` opt-in via Settings / `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1`, and keep `ite8297` dormant.
- Backends: Wire the experimental `ite8910` path to Linux `hidraw` feature reports for actual use without detaching the kernel keyboard driver; installer USB rules now also grant `uaccess` on matching `hidraw` nodes.
- Diagnostics: Improve support guidance for Clevo/TUXEDO-like `0x048d:0x8910` / `0x048d:0x8911` cases and include backend-policy selection reasons in backend probe snapshots.
- Power/Reactive: Avoid redundant startup restore/apply actions when AC/battery policy already matches the current keyboard state; this prevents reactive typing from briefly restarting at brightness 1 and flashing on startup.
- Power/Reactive: Fix reactive temp-dim sync so screen dim now caps actual hardware brightness instead of leaving reactive per-key writes at the old brightness during dim mode.
- Installer: Add a single distro support-profile header so install flows clearly communicate Fedora / Red Hat (tested), Debian / Ubuntu / Linux Mint (experimental), Arch-like (experimental), and openSUSE / other Linux (best-effort) behavior.
- Installer: Improve Debian/Ubuntu/Linux Mint AppImage installs by skipping package-manager work when it is not needed, adding clearer Debian-like messaging, and reducing noisy apt failures when package metadata is unhealthy.
- Installer: For apt-based kernel-driver installs, try both `tuxedo-drivers` and `tuxedo-keyboard`, and point users to TUXEDO package-source docs instead of failing without guidance.
- Tray/UX: Split hardware static-mode switching from the uniform color picker, and hide the picker on brightness-only backends for cleaner capability degradation.
- Docs: Document backend policy, experimental `ite8910` usage, installer `hidraw` permissions, and new environment-variable overrides in the README.

## 0.16.2 (2026-02-08)

- Backends: Add an experimental `asusctl` Aura backend (subprocess-based) for ASUS laptops; includes env toggles and avoids fighting asusd/asusctl dim-sync by default.
- Sysfs: Improve `/sys/class/leds` candidate selection/scoring, expand probe identifiers, and enhance multi-zone + multi-attribute color writes (`multi_intensity`, `color`, `rgb`, and System76 `color_*` files) with helper fallbacks.
- Tray/Power: Tighten idle-power polling logic (debounce + logging) and add/extend unit tests to lock in behavior.
- GUI: Improve Uniform and Reactive Color windows for newer backend capability paths and brightness behavior.

## 0.16.1 (2026-02-04)

- Installer: Add `99-keyrgb-sysfs-leds.rules` udev rule to grant group-write access to keyboard backlight sysfs nodes (e.g. `rgb:kbd_backlight*`) for the `video` group so kernel-backed Clevo/Tuxedo/System76 keyboards can be controlled without polkit prompts.
- Installer: Install both ITE USB (`99-ite8291-wootbook.rules`) and sysfs LED rules by default and trigger `udevadm` for the `leds` subsystem; uninstaller supports removing the sysfs rule when KeyRGB-managed.
- Tray: Improve permission-denied messaging and diagnostics (point users to both the sysfs udev rule and polkit helper paths) and add helpful reproduction steps for maintainers.
- Maintenance: Add tests and installer tweaks to make udev reload/trigger more reliable on conservative stacks (Ubuntu LTS-like setups).

## 0.16.0 (2026-02-03)

- Power: Default `dim` and `dark` profiles now ignore AC/battery brightness override settings.
- Tests: Add strict unit tests to lock in screen-dim brightness sync ordering (prevents dim/restore regressions).
- Typing: Add/extend tray Protocols and reduce `Any`/dynamic attribute coupling across tray/core/gui.
- Maintenance: Replace scattered defensive conversions with `safe_attrs` helpers for clearer, safer reads.
- Docs: README clarifications for backends/status and removed duplicated env-var section.

## 0.15.9 (2026-02-02)

- Build: Add a Code Hygiene build step to detect dynamic attribute coupling, defensive conversions, and `Any` creep.
- Maintenance: Add safe attribute access helpers (`safe_attrs`) with unit tests.
- Maintenance: Add tray state Protocol scaffolding to support gradual typing improvements.
- Fix: Resolve mypy typing issues in tray icon rendering and diagnostics formatting.

## 0.15.8 (2026-01-26)

- Installer: Add “please consider giving the repo a Star” message to end of install flows.
- Uninstall: Suggest opening an issue when uninstalling because KeyRGB didn't work; include diagnostic hints for logs/lsusb/KEYRGB_DEBUG=1.
- Tray: Show a one-time notification when hardware writes fail due to missing permissions (udev/polkit); add permission-detection helpers and wire background effect threads to report permission issues so they no longer fail silently.

## 0.15.7 (2026-01-26)

- Diagnostics/Sysfs: Include detailed sysfs LED permission metadata (mode/uid/gid/ACL), LED driver/module hints, and helper/pkexec/sudo availability to make "permission denied" reports immediately actionable.

## 0.15.6 (2026-01-26)

- Fix: CI/AppImage: AppImage smoke test installs minimal system `libfontconfig`/`libfreetype` in the container (these are intentionally not bundled to avoid GTK/Pango symbol/version conflicts on some distros).

## 0.15.5 (2026-01-26)

- Fix: CI: Import Validation no longer requires tkinter on GitHub Actions Python 3.10 runners (AppImage smoke test still validates the bundled Tk runtime).

## 0.15.4 (2026-01-26)

- Fix: AppImage/Tray: Avoid bundling incompatible `libfontconfig`/`libfreetype` copies that can break the AppIndicator backend on Fedora-like distros (fallback to Xorg tray on Wayland may produce no visible icon).

## 0.15.3 (2026-01-26)

- Fix: Installer: Make udev reload/trigger more reliable on some distros by sending targeted `udevadm trigger --action=add` events and waiting for `udevadm settle` (helps on conservative udev stacks, e.g. some Ubuntu LTS setups).
- Maintenance: Installer: AppImage installs no longer attempt to install Python/Tk/GUI runtime packages; system package changes are reserved for optional kernel drivers / TCC / polkit.
- Documentation: README updated to document the contained AppImage install strategy and standard/full/`--no-system-deps` curl install commands.

## 0.15.2 (2026-01-26)

- Fix: Installer: Fix `tmp: unbound variable` during AppImage downloads by removing an unsafe RETURN trap in the downloader helper (affects `bash install.sh` installs under `set -u`).

## 0.15.1 (2026-01-26)

- Fix: Installer: Avoid `tmp: unbound variable` warnings by ensuring download temp-file cleanup traps don’t leak out of helper functions.
- Fix: GUI: Restore ColorWheel callback invocation for manual RGB entry and make wheel image loading more robust on some Tk builds.
- Fix: AppImage: Bundle Tk / `_tkinter` shared-library dependencies (e.g. `libXft.so.2`) so tkinter imports work on minimal systems.
- Build: Refactor AppImage build helpers into focused modules under `buildpython/steps/appimage/`.
- Maintenance: Remove the legacy AppImage helper shim (`appimage_helpers.py`) after migrating internal imports.

## 0.15.0 (2026-01-25)

- Improvement: Add sysfs multi-zone support (virtual per-key zoning), GUI and tray stability fixes, improved tests, and AppImage packaging updates.
- Refactor: Extract and simplify backend and tray modules (sysfs device, ITE backend, and lighting-controller helpers); refactor `SysfsLedKeyboardDevice` dataclass to use `primary_led_dir`/`all_led_dirs`, centralize per-key zoning logic, and reduce cyclomatic complexity to improve testability and maintainability.
- Fix: Sysfs: Restore missing `_max()` helper, add explicit typing for `zone_lists`, and implement N-zone mapping (Left/Center/Right) with `primary_led_dir` and `all_led_dirs`.
- Fix: Tests: Update `tests/core/test_sysfs_leds_backend_unit.py` to use the new `primary_led_dir` constructor and expand coverage for multi-zone behavior; update tray tests for controller edge cases.
- Build: Add LOC and type checks, fix type annotation issues, and ensure the full build pipeline (Compile, Pytest, Type Check, AppImage) passes.
- Misc: Add `system/udev/99-ite8291-wootbook.rules` for Wootbook ITE permissions and other minor docs/build improvements.

## 0.14.10 (2026-01-23)

- Fix: AppImage: Bundle Tcl/Tk script libraries (`tcl8.6/`, `tk8.6/` directories containing `init.tcl` and support scripts) required by tkinter at runtime.
- Fix: AppImage: Set `TCL_LIBRARY` and `TK_LIBRARY` environment variables in AppRun so tkinter can locate bundled script libraries.
- Note: v0.14.9 bundled only tkinter's native `.so` files but not the Tcl/Tk scripts, causing "Can't find a usable init.tcl" errors when opening GUI windows.

## 0.14.9 (2026-01-23)

- Fix: CI/AppImage: Add missing `libayatana-ido3-0.4-0` package (indicator display objects library) required by Ayatana AppIndicator stack.
- Fix: AppImage: Bundle `libayatana-ido3-0.4.so*` to fix `app_indicator_new` lookup failure on systems without this GTK indicator widget library.
- Note: The v0.14.8 AppImage was missing libayatana-ido3, causing "cannot open shared object file" errors on Fedora/Nobara systems.

## 0.14.8 (2026-01-23)

- Fix: CI/AppImage: Install actual indicator library packages (`libayatana-indicator3-7`, `libappindicator3-1`, etc.) on Ubuntu CI so the bundling step can find and include them.
- Fix: AppImage: Improve library bundling to properly handle symlink chains - recreate symlinks and copy all files in the chain so `libayatana-indicator3.so.7` and related versioned libraries are available at runtime.
- Docs: The v0.14.7 AppImage from CI was missing bundled indicator libraries; v0.14.8 fixes this by installing library packages in CI and improving symlink handling.

## 0.14.7 (2026-01-23)

- Release: CI builds and uploads the AppImage artifact for this tag so users can update directly via the installer or the release page.
- Fix: Verified AppImage bundles indicator libraries (libayatana-indicator3, libindicator3, libappindicator3, libdbusmenu-gtk3) to avoid AppIndicator startup crashes when system packages are missing.
- Fix: Installer: Remove stale temporary download files (`keyrgb.tmp.*`) before downloading and ensure cleanup on EXIT/INT/TERM to avoid leftover temp files after interrupted installs.
- Fix: Tray: Add explicit detection for missing `libayatana-indicator` / `app_indicator_new` and gracefully fall back to the Xorg backend with clear logs.
- Docs: Recommend updating to v0.14.7 to receive the bundled AppImage and installer robustness improvements.

## 0.14.6 (2026-01-23)

- Fix: Tray: Improve fallback to Xorg backend when AppIndicator libraries are missing, preventing startup crashes on systems without indicator libraries until the v0.14.5+ AppImage is deployed.
- Tray: Add explicit error detection for missing `libayatana-indicator` / `app_indicator_new` to log clearer fallback reasons.

## 0.14.5 (2026-01-23)

- Fix: AppImage: Bundle missing indicator dependencies (libayatana-indicator3, libindicator3, libdbusmenu-gtk3) so native tray icons work and the tray app no longer crashes on systems that don't provide these packages.
- Fix: AppImage: Improve AppIndicator bundling to include the full dependency chain (not only top-level libappindicator) for reliable desktop integration.
- Fix: Installer: Clean up stale temporary download files (`keyrgb.tmp.*`) before starting a new download, and add an EXIT/INT/TERM trap to ensure temp files are removed on interrupt.
- Docs: Clarified that the AppImage bundles indicator libraries and that the installer updates the AppImage by downloading to a temporary file and atomically moving it into place.

## 0.14.4 (2026-01-23)

- AppImage: Bundle tkinter native libraries (libtk8.6, libtcl8.6) directly into AppImage to eliminate system `python3-tk` dependency.
- AppImage: Bundle libappindicator3/ayatana-appindicator3 for native tray icon support without requiring system packages.
- AppImage: Now fully self-contained and portable - works out-of-the-box on any distro without system dependencies.
- Installer: Updated installer state tracking to detect and auto-update stale AppImage versions (tracks `last_tag`).
- Installer: Enhanced uninstaller parity - removes KeyRGB-managed files even when versions differ (uses content markers as fallback).
- Docs: Clarified README install instructions - AppImage is truly standalone; system deps only needed for development/clone installs.

## 0.14.3 (2026-01-22)

- Backends: Sysfs LED backend can operate on root-only `/sys/class/leds/*kbd_backlight*` via a privileged helper (pkexec/polkit), avoiding running the whole app as root.
- Diagnostics: Sysfs LED snapshot now reports inferred keyboard lighting zones (e.g. `rgb:kbd_backlight`, `_1`, `_2`).
- Effects: Unsupported hardware effects (e.g. `rainbow` on sysfs backends) fall back gracefully instead of raising.
- Dev: Vendored driver reference added: `vendor/tuxedo-drivers-4.11.3` (unignored) with local ignore rules for build artifacts.

## 0.14.2 (2026-01-18)

- Refactor: Installer modernization - split monolithic `install.sh` into modular scripts under `scripts/lib/` for improved maintainability and testability.
- Installer: New `scripts/install_dev.sh` for developer installations (editable pip install mode).
- Installer: New `scripts/install_user.sh` for end-user installations (AppImage mode).
- Installer: New `scripts/uninstall.sh` for modular uninstall operations.
- Installer: Modular library components in `scripts/lib/` (common_core, state, optional_components, privileged_helpers, user_integration, user_prompts).
- Installer: Legacy monolithic installers preserved in `scripts/legacy/` for reference and backward compatibility testing.
- Installer: Root `install.sh` and `uninstall.sh` now invoke modular scripts while maintaining backward compatibility.
- Docs: Updated README screenshots for reactive typing feature.
- Improvement: Cache config file mtime to short-circuit frequent `reload()` calls and avoid unnecessary disk I/O from pollers.
- Fix: Add resume grace period (ignore transient screen-off/dim for ~3s after resume) and increase idle dim debounce thresholds to reduce visible brightness flicker on some systems.
- Build: Updated `.gitignore` for installer state and temporary files.

## 0.14.1 (2026-01-11)

- Fix: Restore Reactive Typing brightness slider functionality (fixed regression where 1-100% looked identical).
- Fix: Allow reactive pulses to exceed dim profile brightness by raising hardware brightness when needed (pulses no longer capped to a dim backdrop).
- Fix: Ensure reactive pulses are suppressed when `reactive_brightness` is set to 0.
- Fix: Improve reactive animation visibility for uniform-only (non-per-key) backends by using representative peak-color mixing.
- Tests: Updated reactive rendering unit tests to cover new brightness-raising policy and temp-dim capping.

## 0.14.0 (2026-01-11)

- Fix: Prevent random brightness flashes around screen-dim by adding hysteresis to backlight dim detection and no-op guards in temp-dim policy/actions to stop repeated dim↔restore cycling.
- Fix: Ensure `dim_to_temp` does not reapply when already active and avoid restarting fades; restore path uses fade-in to prevent abrupt jumps.
- Fix: Tray icon brightness now follows base/profile brightness (not reactive pulse intensity) and avoids black icon on dim profiles; adjusted icon scaling mapping so icon remains visible at low brightness.
- Fix: Reactive typing behavior improvements: split persisted `reactive_brightness` (pulse intensity) from base brightness, add dedicated UI slider for reactive brightness, and fix stale slider values and unexpected intensity-driven icon regressions.
- Improvement: Smoother fades for dim/undim and fade-in on restore; tuned durations so 'off' is quick and 'dim' is gradual.
- GUI: Per-key and calibrator UI sizing/label wrapping fixes and prevent tiny startup geometry flashes.
- Tests: Add unit tests covering hysteresis, temp-mode non-repeat, tray icon color selection, and reactive brightness behavior; full test suite passing.

## 0.13.4 (2026-01-09)

- Tray: Replace the placeholder tray icon with the branded KeyRGB logo while keeping the “only the K changes color” illusion via a mask-based compositing pipeline (with theme-aware outline inversion).
- Tray: Improve representative-color selection for multi-color/per-key/rainbow-like effects with low CPU cost and caching.
- Tray: Reduce config polling noise by skipping no-op rewrites and improve apply-event cause propagation in logs.
- GUI: Production polish pass for sizing and theming (theme-safe ColorWheel rendering, responsive layouts, and improved per-key editor selection visibility).
- Packaging: Expand tray logo discovery paths and ensure the AppImage build bundles the tray logo asset.

## 0.13.3 (2026-01-08)

- Fix: Reduce remaining dim-time flashing by minimizing lock hold time and pre-reading config values before applying restore brightness; this removes the extra one-frame delay on restore after screen-dim events.
- Perf: Optimize `dim_to_temp` and `restore_brightness` paths to acquire the engine device lock for the shortest possible window and perform per-key/main brightness updates atomically.
- Tests: Update unit tests to reflect atomic reactive brightness updates and add traces to validate single-frame transitions.
- Docs: Clarify troubleshooting steps for brightness traces and the `KEYRGB_DEBUG_BRIGHTNESS` capture process.

## 0.13.2 (2026-01-07)

- Fix: Prevent brief brightness flashes when restoring from screen dim/suspend by synchronizing brightness updates and render-time brightness resolution; this eliminates one-frame stale or mixed brightness frames on restore and at startup for reactive effects.
- Fix: Make reactive idle-power updates atomic (update `engine.per_key_brightness` and call `engine.set_brightness()` together under the engine device lock) to avoid mixed-state intermediate frames.
- Tests: Add unit tests and logging for brightness behavior and idle-power actions; tests assert no stale-brightness frames and verify device call logging under `KEYRGB_DEBUG_BRIGHTNESS=1`.
- Docs: Document `KEYRGB_DEBUG_BRIGHTNESS` debug logging and how to capture brightness traces for troubleshooting.

## 0.13.1 (2026-01-07)

- Fix: Avoid brief brightness flashes/flicker when restoring from screen dim/suspend by ensuring the effects engine starts fades from black instead of a stale color.
- Tests: Add unit tests to assert restore clears previous color and prevents transient hardware brightness writes.
- Maintenance: Stop re-exporting underscore internal helpers from `src.core.tcc_power_profiles` and update tests to import them directly.

## 0.13.0 (2026-01-07)

- Refactor: Reduced cyclomatic complexity for radon E-rated hotspots by extracting helpers while preserving public interfaces and test behavior. Targeted items: `buildpython/steps/step_quality.py::code_markers_runner`, `src/core/diagnostics/collectors_backends.py::backend_probe_snapshot`, `src/gui/perkey/overlay/autosync.py::auto_sync_per_key_overlays`, `src/gui/theme/detect.py::detect_system_prefers_dark`.
- Build: Added build-time check steps and runners (`black` check, LOC check, `mypy` type check) and updated the build runner steps to include them.
- Core: Refactored diagnostics, backend probing, effects engine/fades, per-key animation, and profile loading; added `src/core/utils/exceptions.py` and new software effects modules for better isolation and testability.
- GUI: Extracted and simplified UI helpers (per-key canvas drawing/events, color wheel UI), updated reactive color/uniform windows, and improved layout/geometry helpers.
- Tray: Refactored controllers and pollers (split `config_polling` into core/helpers, added idle-power helpers/actions and lighting-controller helpers) to improve testability and reduce complexity.
- Tests: Added and reorganized numerous unit tests covering power manager, profile storage, config polling, idle/power polling, and reactive/backdrop behaviors; tests pass locally and are included in CI.
- Quality: Cyclomatic complexity re-run shows **E-rated blocks: 0** and the full build profile is green (Compile, Pytest, Ruff lint/format, Import Validation/Scan, Code Markers, File Size, LOC Check, Type Check, AppImage build).
- Release: Tagged as `v0.13.0` (beta) and published as a GitHub prerelease; AppImage for `v0.13.0` is available and the installer uses this prerelease by default when selecting the beta channel.
- Notes: This release groups multiple refactors and test coverage improvements; see individual commits and the release notes for file-level details and test lists.

## 0.12.3 (2026-01-06)

- Fix: reduce likelihood of crashes after a USB disconnect by aggressively stopping further USB I/O and marking the device unavailable.
- Fix: ensure per-key disconnect handling marks the device unavailable while holding the device lock to reduce race windows that could lead to libusb crashes.
- Maintenance: centralize USB error classification (device disconnected/busy) to reduce duplicated, inconsistent errno/string checks across tray/effects/GUI (`src/core/utils/exceptions.py`).
- Refactor: extract config property factory helpers into `src/core/config/_props.py` and simplify `src/core/config/config.py` (reduced LOC and clearer property helpers).
- Tests: add unit tests to cover brightness-split behavior, disconnect-safe effect rendering, and software-effects visibility (`tests/core/test_brightness_split_unit.py`, `tests/core/test_effects_render_disconnect_unit.py`, `tests/core/test_software_effects_visibility_unit.py`).
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
