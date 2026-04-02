## Issue 5: Secondary ITE `0x048d:0x7001` lightbar support

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/5

Status as of 2026-04-01:

- The codebase now contains a real issue-5 implementation path, not just a dormant scaffold.
- The remaining work is primarily real hardware testing on a machine that actually exposes the secondary `0x048d:0x7001` device.
- This document captures the current implementation state, verification signal, tester workflow, and the known open validation gaps so work can resume later without reconstructing the session.

## Goal of issue #5

Support the secondary Tongfang/MECHREVO ITE HID device `0x048d:0x7001` as a separate auxiliary lighting surface, most likely a front lightbar, instead of pretending it is part of the main keyboard backend.

The intended product model is:

- Primary keyboard controller:
  - `0x048d:0x600b`
  - existing `ite8291r3` path
- Secondary auxiliary controller:
  - `0x048d:0x7001`
  - new `ite8233` path
  - treated as `lightbar`

## What the current working tree now provides

### 1. Experimental `ite8233` backend

- `src/core/backends/ite8233/`
- Status:
  - promoted from dormant to `experimental`
  - evidence tag: `reverse_engineered`
- Scope:
  - single-zone uniform color
  - brightness
  - off
- Transport:
  - `hidraw`
- Explicit opt-in required:
  - Settings experimental-backend toggle, or
  - `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1`

The backend intentionally does not yet claim per-segment lightbar control or firmware effects.

### 2. Multi-device discovery and support flow

- `src/core/diagnostics/device_discovery.py`
- `src/core/diagnostics/additional_evidence.py`
- `src/core/diagnostics/support_reports.py`
- `src/gui/windows/support.py`

The app now has a tray-first support workflow that can:

- run the existing diagnostics snapshot
- run a new device-discovery scan
- classify candidates as:
  - `supported`
  - `experimental_disabled`
  - `known_dormant`
  - `known_unavailable`
  - `unrecognized_ite`
- export:
  - diagnostics JSON
  - discovery JSON
  - full support bundle JSON
- generate issue-template-aware draft text
- optionally run deeper evidence collection for unsupported devices:
  - `lsusb -v`
  - `usbhid-dump -e descriptor`

This is meant to make future issue-5-style reports much more actionable.

### 3. Tray device-context model

- `src/tray/ui/menu.py`
- `src/tray/ui/menu_status.py`
- `src/tray/ui/menu_sections.py`
- `src/tray/controllers/secondary_device_controller.py`

The tray no longer assumes a keyboard-only menu body.

The top status rows are now selectable device contexts:

- `Keyboard: ...`
- `Lightbar: ...`

When the lightbar context is selected and the backend is usable, the tray exposes real lightbar actions:

- `Color…`
- `Brightness`
- `Turn Off`

When the device is detected but not usable, the tray shows an honest status instead of dead controls.

### 4. Per-key editor lightbar overlay support

- `src/gui/perkey/lightbar_controls.py`
- `src/gui/perkey/lightbar_layout.py`
- `src/gui/perkey/canvas_impl/_canvas_drawing.py`

The per-key editor now has a conditional `Lightbar` panel under `Overlay alignment` when a lightbar device is detected.

The overlay state is profile-backed and supports:

- visibility toggle
- length
- thickness
- x offset
- y offset
- inset
- save/reset

This is a placement preview only. It does not imply per-segment hardware control.

### 5. Software-effect targeting for auxiliary devices

- `src/core/effects/software_targets.py`
- `src/tray/controllers/software_target_controller.py`

The effects engine is still keyboard-centric for acquisition and per-key rendering, but looped software and reactive effects now have a real target policy:

- `keyboard`
- `all_uniform_capable`

When `all_uniform_capable` is selected, compatible auxiliary devices like the `ite8233` lightbar receive a uniformized mirror of the software/reactive output.

The implementation also restores the auxiliary device's configured static state when leaving shared software ownership.

## Current tester-facing workflow

### Standard tray launch with experimental backends enabled

```bash
KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 ./keyrgb
```

Expected on hardware with both devices:

- normal keyboard backend selection still works
- the tray should show a separate `Lightbar` context row if `0x7001` is discovered
- the support tools discovery scan should surface the auxiliary device explicitly

### Forced issue-5 backend test path

```bash
KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 KEYRGB_BACKEND=ite8233 ./keyrgb
```

Expected on real `0x7001` hardware:

- the app should bind the experimental `ite8233` backend
- uniform color, brightness, and off should work on the lightbar path

Expected on a machine without `0x7001`:

- predictable failure or unavailable probe state
- no false claim that the backend is usable

### Support tools launch path

Debug focus:

```bash
python -m src.gui.windows.support
```

Discovery focus:

```bash
KEYRGB_SUPPORT_FOCUS=discovery python -m src.gui.windows.support
```

Expected support flow for issue #5 testing:

1. Save a support bundle before testing.
2. Run the discovery scan with experimental backends disabled.
3. Enable experimental backends.
4. Rerun discovery and save a second bundle.
5. Test tray lightbar controls and software-target routing.
6. Save post-test evidence if something fails.

## Verification completed in this session

### Focused automated verification

The current issue-5 surfaces were verified with a focused pytest sweep.

Result:

- `213 passed in 0.52s`

Covered areas included:

- `ite8233` backend and protocol
- discovery and additional-evidence collection
- support bundle and issue-report generation
- support window UI
- config persistence for:
  - `software_effect_target`
  - `tray_device_context`
  - `lightbar_color`
  - `lightbar_brightness`
- tray device-context switching
- secondary lightbar actions
- software-target policy and restore behavior
- lightbar overlay and per-key editor surfaces

Representative suites used during the verification pass:

- `tests/core/test_ite8233_backend_unit.py`
- `tests/core/test_device_discovery_unit.py`
- `tests/core/test_additional_evidence_unit.py`
- `tests/core/test_support_reports_unit.py`
- `tests/gui/test_support_window_unit.py`
- `tests/tray/test_tray_application_unit.py`
- `tests/tray/test_tray_menu_capabilities_unit.py`
- `tests/tray/test_tray_secondary_device_controller_unit.py`
- `tests/tray/test_tray_software_target_controller_unit.py`

### Runtime smoke checks completed

- Tray startup now gets past the previous pystray menu-construction crash and reaches normal startup.
- The support tools window launches cleanly.
- A later second-launch smoke test hit the normal single-instance guard because an existing tray process was already running, not because of a new regression.

### Static/editor validation completed

Checked files such as:

- `src/core/backends/ite8233/backend.py`
- `src/gui/windows/support.py`
- `src/tray/ui/menu.py`
- `src/tray/controllers/software_target_controller.py`

No editor/language-service errors were reported in the verification pass.

## What is still not verified

The remaining gaps are hardware-only, not obvious code or test gaps.

### Real `0x7001` device behavior still needed

Still needs confirmation on actual issue-5-style hardware:

- detection of `0x048d:0x7001`
- correct tray `Lightbar` context appearance
- color write behavior
- brightness behavior
- off behavior
- relaunch behavior
- suspend/resume behavior
- interaction with the `Software Targets` policy

### Multi-device runtime behavior still needs on-device confirmation

The architecture now supports a clean multi-device model, but the following should still be validated on real hardware:

- keyboard path remains unaffected when a secondary lightbar is present
- auxiliary restore behavior is correct after leaving shared software targeting
- no unexpected fighting between static lightbar state and software-target mirroring
- no permission or hidraw edge cases unique to the actual reporter hardware

## Suggested real hardware test checklist

Use this when resuming issue #5 testing on a real `0x7001` machine.

1. Launch with:

```bash
KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 ./keyrgb
```

2. Open `Support Tools…` and save:
   - diagnostics JSON
   - discovery JSON
   - full support bundle

3. Confirm discovery shows both:
   - keyboard controller
   - `lightbar` device context for `0x048d:0x7001`

4. Select the `Lightbar` tray context and test:
   - `Color…`
   - `Brightness`
   - `Turn Off`

5. Return to the keyboard context and test `Software Targets`:
   - `Keyboard Only`
   - `All Compatible Devices`

6. With `All Compatible Devices` enabled, run a software or reactive effect and verify:
   - keyboard still behaves correctly
   - lightbar mirrors the uniformized output

7. Switch back to `Keyboard Only` and verify the lightbar restores to its configured static state.

8. Test relaunch.

9. Test suspend/resume if safe.

10. Save another support bundle after testing, especially if anything fails.

## Relevant files and docs for later resume

Primary implementation areas:

- `src/core/backends/ite8233/`
- `src/core/diagnostics/device_discovery.py`
- `src/core/diagnostics/additional_evidence.py`
- `src/core/diagnostics/support_reports.py`
- `src/gui/windows/support.py`
- `src/tray/controllers/secondary_device_controller.py`
- `src/tray/controllers/software_target_controller.py`
- `src/tray/ui/menu.py`
- `src/tray/ui/menu_status.py`
- `src/gui/perkey/lightbar_controls.py`
- `src/gui/perkey/lightbar_layout.py`

Supporting docs:

- `docs/developement/backends/ite8233-lightbar-research.md`
- `docs/developement/diagnostics-discovery-roadmap.md`
- `CHANGELOG.md` (`0.19.2`)

## Current conclusion

The codebase is ready for issue-5 real hardware testing.

What remains is no longer broad implementation work; it is targeted on-device validation of the experimental `ite8233` path and the new support-tool workflow on a machine that actually exposes the secondary `0x048d:0x7001` lightbar controller.