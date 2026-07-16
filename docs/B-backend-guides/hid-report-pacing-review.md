# HID Report Pacing — Publishing Review Doc

## Summary

Back-to-back HID reports were causing the ITE8291r3 controller (and potentially other ITE USB controllers) to blank, flicker, or reset. We now enforce a small bus-quiet delay between consecutive HID reports on all USB/HID backends.

## What Changed

- Added a shared helper module: `src/core/backends/_report_pacing.py`
  - Default delay: `1 ms` (`DEFAULT_HID_REPORT_DELAY_S = 0.001`)
  - Global env override: `KEYRGB_HID_REPORT_DELAY_MS`
  - Per-backend env override: `KEYRGB_<BACKEND_NAME>_REPORT_DELAY_MS`, with backend punctuation normalized to underscores
  - Setting the variable to `0` disables pacing.

## Backends Now Using Pacing

The following backends now sleep after each HID feature or output report:

| Backend | Path |
|---------|------|
| `ite8291r3` | `src/core/backends/ite8291r3/device.py` + `backend.py` |
| `ite8291` | `src/core/backends/ite8291/hidraw.py` |
| `ite8291-zones` | `src/core/backends/ite8291/hidraw.py` |
| `ite8295-zones` | `src/core/backends/ite8291/hidraw.py` |
| `ite8910` | `src/core/backends/ite8910/hidraw.py` |
| `ite8233` (experimental) | `src/core/backends/ite8910/hidraw.py` |
| `ite8297` (experimental) | `src/core/backends/ite8910/hidraw.py` |
| `ite8258` (experimental) | `src/core/backends/ite8291/hidraw.py` |
| `ite8258-chassis` (experimental, shared proxy) | `src/core/backends/ite8291/hidraw.py` + `src/core/backends/shared_hidraw_transport.py` |

Backends intentionally **not** changed:

- `sysfs-leds` — kernel sysfs writes, not raw HID reports
- `sysfs-mouse` — same reasoning
- `asusctl-aura` — D-Bus to asusctl daemon, not direct HID

## User-Facing Env Variables

| Variable | Purpose |
|----------|---------|
| `KEYRGB_HID_REPORT_DELAY_MS` | Global override for all HID backends (default `1`) |
| `KEYRGB_<BACKEND>_REPORT_DELAY_MS` | Per-backend override for HID pacing. Backend punctuation is normalized to underscores, so `ite8258_perkey_chassis` uses `KEYRGB_ITE8258_PERKEY_CHASSIS_REPORT_DELAY_MS`. Falls back to the global value if unset. |

## Reactive Typing Idle Traffic Reduction

- `src/core/effects/reactive/_render_runtime.py` now skips duplicate rendered per-key frames for backends that set `reassert_every_frame=True`, reducing unnecessary reports while still honoring per-frame reassert when the frame actually changes.

## Diagnostics

- `src/core/diagnostics/snapshots.py` now captures `KEYRGB_HID_REPORT_DELAY_MS` alongside known per-backend report-delay overrides.

## Documentation

- `README.md` updated with the new `KEYRGB_HID_REPORT_DELAY_MS` variable and clarified the per-backend fallback behavior.

## Validation

- `tests/core/backends/ite/test_ite8291r3_native_backend_unit.py` — updated to patch the shared pacing helper and added a global-fallback test.
- Release profile: **2885 passed, 1 skipped**; AppImage build and smoke test passed.
- `ruff check` and `mypy` clean on changed source files.

## Risk / Notes for Publishing Agent

- This is a behavior change for HID backends: every HID report now has a 1 ms delay by default. In the worst case, a full per-key frame on `ite8291r3` adds ~13 ms, which is imperceptible for effects.
- The user already validated the 1 ms `ite8291r3` pacing in production and reported no blanking.
- The running AppImage process (`~/.local/bin/keyrgb.AppImage`) is the old binary and must be restarted for these changes to take effect.
