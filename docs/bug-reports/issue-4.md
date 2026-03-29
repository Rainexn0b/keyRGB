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

## Assessment after 0.18.3

0.18.3 improved the ITE8910 backend substantially, but it did not fully close this issue.

### Confirmed fixed by current follow-up work

- Hardware effect speed inversion:
	- Confirmed root cause in `src/core/effects/hw_payloads.py` where the generic legacy hardware-speed inversion was still applied to `ite8910`.
	- `ite8910` now treats larger raw speed values as faster, matching the documented firmware contract in `src/core/backends/ite8910/protocol.py`.
	- Fix: use direct UI speed for `ite8910`, keep legacy inverted mapping for older hardware backends.

- Software effect blinking:
	- Confirmed likely root cause in `src/core/backends/ite8910/device.py` where `set_key_colors(..., enable_user_mode=False)` still called `reset()` and rewrote the full keyboard to black before each frame.
	- Software and reactive per-key render loops intentionally call `set_key_colors(..., enable_user_mode=False)` after user mode has already been enabled.
	- Fix: for `ite8910`, skip the reset/brightness re-init path when `enable_user_mode=False` so per-frame writes do not visibly blank the keyboard.

- X58xWNx per-key row inversion / wrong-key mapping:
	- Confirmed root cause in the `ite8910` tuple translation path.
	- KeyRGB's saved keymaps and built-in reference profiles use a bottom-up logical row convention (`esc` on row 5, `lctrl` on row 0 in the reference defaults), but the `ite8910` backend was encoding tuple rows as if row 0 were the top row.
	- Fix: flip the logical row before encoding the ITE8910 LED id so `(row, col)` tuples match the same KeyRGB convention used by the existing keymaps and calibrator UX.

- Calibrator/editor matrix mismatch:
	- Confirmed root cause in the calibrator using a hard-coded 6x21 probe grid while the `ite8910` backend reports 6x20.
	- Fix: use the selected backend dimensions for the calibrator probe session and sanitize stale out-of-range keymap/color cells on load.

- ISO visual layout support:
	- Confirmed UI limitation in the bundled reference layout, which only exposed the ANSI row around left shift.
	- Fix: add the ISO-only key next to left shift to the built-in reference layout and map `KEY_102ND` to the same `key_id` for reactive/keymap consistency.

### Remaining validation need

- Hardware confirmation on the reporter's X58xWNx:
	- The root causes above are now identified and corrected in code, but the final proof still comes from on-device confirmation.
	- No additional unfixed code path is currently known for issue #4 after these changes.

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
	- Software effects render per-key frames through `set_key_colors(..., enable_user_mode=False)`.

- `src/core/effects/reactive/_render_runtime.py`
	- Reactive effects do the same after mode init.

- `src/core/resources/layout.py`
	- The visual layout was ANSI-only around left shift before the follow-up ISO hitbox addition.

- `src/gui/calibrator/app.py`
	- The calibrator probe grid was hard-coded to 6x21 instead of using the active backend dimensions.

- `vendor/ite8291r3-ctl/README.md`
	- Documents the older `ite8291r3` hardware-effect speed scale as `0 = fastest, 10 = slowest`, which is why the legacy inversion cannot be removed globally.

## Current status

- 0.18.3 alone: not sufficient to close issue #4.
- Current working tree after this follow-up:
	- fixes the confirmed speed inversion bug
	- fixes the likely software blinking cause
	- fixes the X58xWNx logical row inversion in the `ite8910` tuple translation
	- fixes the calibrator's backend-dimension mismatch
	- adds ISO-only visual key support for calibration/editor use
	- still needs on-device confirmation from the reporter before closing the GitHub issue
