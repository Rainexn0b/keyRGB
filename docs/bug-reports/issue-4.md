## Issue 4: ITE8910 bugs on Clevo X58xWNx

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/4

Reporter environment:

- KeyRGB 0.18.2
- Linux Mint 22.3 / Cinnamon
- Clevo X58xWNx
- ITE 8910 (`0x048d:0x8910`) selected through the `ite8910` backend

## Reported symptoms

1. Keymap calibrator shows an ANSI-style visual keyboard, so some ISO-only keys cannot be assigned.
2. Per-key editor lights the wrong physical key on some assignments, with an apparent top-row/bottom-row inversion.
3. Software effects blink on and off.
4. Hardware effect speed is reversed: lower UI values run faster and higher UI values run slower.

## Assessment after current follow-up work

The current working tree now covers the non-speed items from issue #4 with
both implementation changes and focused regression tests. The remaining
materially open complaint is the reporter's later note that the effective
hardware speed range on `ite8910` still feels too narrow.

For this version, that means issue #4 is functionally complete except for the
speed-range complaint that now depends on a returned Support Tools bundle with
the guided backend-speed probe results.

### Confirmed fixed by current follow-up work

- Hardware effect speed inversion:
	- Confirmed root cause in `src/core/effects/hw_payloads.py` where the generic legacy hardware-speed inversion was still applied to `ite8910`. 
	- `ite8910` now treats larger raw speed values as faster, matching the documented firmware contract in `src/core/backends/ite8910/protocol.py`.
	- Fix: use direct UI speed for `ite8910`, keep legacy inverted mapping for older hardware backends.

- Software effect blinking:
	- One confirmed cause was fixed in `src/core/backends/ite8910/device.py`: incremental `set_key_colors(..., enable_user_mode=False)` no longer resets and rewrites the full keyboard to black before each frame.
	- The generic software-render path in `src/core/effects/software/base.py` now tracks mode-init state, so per-key software frames do not re-enter user mode on every render.
	- This is now ratcheted by unit tests that lock in one-time mode initialization plus incremental per-key writes; hardware confirmation is still useful, but the known root causes are covered.

- X58xWNx per-key row inversion / wrong-key mapping:
	- Confirmed root cause in the `ite8910` tuple translation path.
	- KeyRGB's saved keymaps and built-in reference profiles use a bottom-up logical row convention (`esc` on row 5, `lctrl` on row 0 in the reference defaults), but the `ite8910` backend was encoding tuple rows as if row 0 were the top row.
	- Fix: flip the logical row before encoding the ITE8910 LED id so `(row, col)` tuples match the same KeyRGB convention used by the existing keymaps and calibrator UX.

- Calibrator/editor matrix mismatch:
	- Confirmed root cause in the calibrator using a hard-coded 6x21 probe grid while the `ite8910` backend reports 6x20.
	- Fix: use the selected backend dimensions for the calibrator probe session and sanitize stale out-of-range keymap/color cells on load.

- Physical layout support in editor/calibrator:
	- The old ANSI/ISO-only toggle has been replaced with a layout catalog under `src/core/resources/layouts/`.
	- KeyRGB now exposes `auto`, `ansi`, `iso`, `ks`, `abnt`, and `jis` as backend-independent physical-layout variants.
	- Layout resolution is cached, auto-detect is conservative on generic laptop AT keyboard nodes, and the per-key editor now exposes layout selection in the shared Keyboard Setup pane.
	- The canvas now resolves geometry from the active layout first, so shared key IDs like `enter` use the correct physical hitbox for the selected layout.

### Remaining validation need

- Hardware confirmation on the reporter's X58xWNx is still useful as a final
	sanity check.
- From a code and regression perspective, the remaining materially open item is
	the reported narrow hardware-speed range on `ite8910`.
- That remaining speed complaint is intentionally evidence-gated now: the next
	useful step is a returned support bundle containing the guided `ite8910`
	backend-speed probe observations added in this follow-up work.

## Code evidence used for assessment

- `src/core/effects/hw_payloads.py`
	- Generic hardware payload builder still inverted UI speed for all backends before the follow-up fix.

- `src/core/backends/ite8910/protocol.py`
	- Documents `0x00..0x0A` speed values with larger values meaning faster firmware animation.

- `src/core/backends/ite8910/device.py`
	- `reset()` clears all LEDs to black.
	- `set_key_colors(..., enable_user_mode=False)` previously still called `reset()` + `set_brightness()`, which is a bad fit for per-frame software/reactive rendering.

- `src/core/backends/ite8910/protocol.py`
	- The tuple-to-LED translation previously treated row 0 as the top row instead of the existing KeyRGB bottom-up logical convention.

- `src/core/effects/software/base.py`
	- Software effects render per-key frames through `set_key_colors(..., enable_user_mode=False)` and now track per-mode init state so user mode is only re-entered on the first per-key frame or when a brightness update has to fall back.

- `src/core/effects/reactive/_render_runtime.py`
	- Reactive effects do the same after mode init.

- `src/core/resources/layout.py`
	- The reference visual layout now supports named physical variants instead of only a boolean ANSI/ISO toggle.

- `src/core/resources/layouts/`
	- New catalog/detect API package that decouples physical layout selection from backend probing.

- `src/gui/calibrator/app.py`
	- The calibrator probe grid now uses the active backend dimensions instead of a hard-coded 6x21 matrix.


- Historical `ite8291r3-ctl` protocol notes
	- Documents the older `ite8291r3` hardware-effect speed scale as `0 = fastest, 10 = slowest`, which is why the legacy inversion cannot be removed globally.

## Current status

- 0.18.3 alone: not sufficient to close issue #4.
- Current working tree after the follow-up and UX split:
	- fixes the confirmed speed inversion bug, though the later speed-range complaint on `ite8910` remains open
	- fixes the X58xWNx logical row inversion in the `ite8910` tuple translation
	- fixes the calibrator's backend-dimension mismatch
	- ratchets the software-render flashing fix through tests that lock in one-time mode init plus incremental per-key writes on `ite8910`
	- replaces the old ANSI/ISO-only overlay model with explicit physical-layout variants and an on-demand Keyboard Setup pane for calibration/editor use
	- is functionally complete for the non-speed items in issue #4, with on-device reporter confirmation still useful as a final sanity check

## End-of-version closure view

For the latest reporter complaints, the state for this version is:

1. Layout and calibrator/editor mismatches:
	- addressed through the physical-layout catalogue, backend-dimension-aware calibrator wiring, and slot-first layout/keymap plumbing.
2. Wrong per-key assignment and multi-LED logical keys:
	- addressed through corrected `ite8910` tuple translation plus one-logical-key-to-many-cells keymap support across storage, calibrator, editor, and reactive typing.
3. `ite8910` software blinking:
	- addressed in code by switching per-key software/reactive rendering to backend-specific mode-maintenance policy, with `ite8910` using one-time init instead of per-frame reset; hardware retest is still desirable, but the known root causes are covered.
4. `ite8910` hardware-speed complaint:
	- still open, but no longer blocked on code discovery. The required next step is the support bundle with the guided backend-speed probe data.

Locale-specific legend polish remains intentionally deferred and is not a release blocker for closing the current issue-4 implementation batch.

## Follow-up: physical layout setting (post-0.18.6)

The 0.18.4 ISO key addition solved the problem for ISO users, but ANSI users
(including the maintainer's `ite8291r3` hardware) now see the extra `<>` key
even though their physical keyboard does not have it.

### Reported (latest update from reporter, 0.18.6)

1. ISO layout is not complete (e.g. right CTRL not present) — suggests a
   physical layout selector.
2. Rows are now aligned with actual keyboard rows. ✓
3. LEDs still flash when using any software effect on `ite8910`.
4. Hardware effect speed now has not much difference between speed 1 and 10
   on `ite8910`.

### Fix: configurable physical layout catalog

- Added `physical_layout` config setting with `"auto"` (default), `"ansi"`,
	`"iso"`, `"ks"`, `"abnt"`, and `"jis"`.
- Auto-detect still probes `/sys/class/input/*/capabilities/key` for
	`KEY_102ND` (evdev code 86), but generic `AT Translated Set 2 keyboard`
	nodes are now treated as inconclusive instead of forcing ISO.
- Layout resolution falls back conservatively to ANSI when detection is
	inconclusive.
- Per-key editor, calibrator, and overlay autosync use the resolved layout
	variant so hidden keys are not drawn or hit-testable.
- The per-key editor exposes the choice in the shared Keyboard Setup pane, and
	Settings still mirrors the same config value.

### Remaining items from reporter update

- Software blinking on `ite8910` — the old incremental-update reset path is
	fixed, and the generic software renderer now tracks mode init state instead of
	re-entering user mode on every per-key frame. The known root causes are now
	covered by tests; device confirmation is still useful, but this is no longer a
	known unratcheted gap.
- Hardware speed range compression on `ite8910` — speed works correctly on the
	maintainer's `ite8291r3`; `ite8910` may need a different speed-scale mapping
	or the firmware's speed range is genuinely narrower.
- Layout completeness is improved further: the shared ANSI/ISO/ABNT bottom-row
	overlay now exposes right Ctrl in addition to the existing Menu key. Broader
	regional completeness beyond that still depends on the reference layout model.

## Regression coverage snapshot

- `tests/core/test_ite8910_translation_unit.py`
	- locks in the bottom-up logical row translation and the incremental `set_key_colors(..., enable_user_mode=False)` behavior for `ite8910`
- `tests/core/test_hw_payloads_unit.py`
	- locks in the direct speed policy for `ite8910`
- `tests/core/test_software_render_mode_init_unit.py`
	- locks in one-time per-key mode initialization and no redundant user-mode re-entry on later software frames
- `tests/gui/test_calibrator_app_unit.py`
	- locks in calibrator use of backend-reported matrix dimensions
- `tests/core/test_reference_layout_unit.py`
	- locks in the physical-layout catalog behavior used by editor/calibrator layout selection
- `tests/gui/test_perkey_setup_panels_unit.py`
	- locks in the current UX split between always-visible lighting profiles and the shared setup pane used for Keyboard Setup and Overlay Editor
