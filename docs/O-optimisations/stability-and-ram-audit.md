# Runtime Stability and RAM Usage Audit

**Date:** 2026-04-30
**Scope:** Full codebase analysis targeting runtime stability and memory efficiency.

---

## Scores

| Category | Score | Trend |
|---|---|---|
| Runtime Stability | **7.5 / 10** | Baseline — defensive patterns are solid, resource cleanup gaps identified |
| RAM Usage | **8.0 / 10** | Baseline — no leaks; optimisation targets are baseline footprint reductions |

---

## Runtime Stability Analysis

### Strengths

1. **Exception-transparency boundaries** — Tuple-typed caught exceptions with `@quality-exception exception-transparency` comments throughout. Expected runtime failures are contained; unexpected defects propagate.
2. **`NullKeyboard` sink pattern** — Effect engine falls back to a no-op device when hardware is unavailable, keeping the tray functional.
3. **Backend exception hierarchy** — `BackendPermissionError(BackendError, PermissionError)` etc. preserves `isinstance` compatibility with Python builtins.
4. **Atomic config writes** — `file_storage.py` uses temp + `os.replace()` preventing corruption from concurrent writers.
5. **Config mtime+digest caching** — `Config.reload()` short-circuits when the file hasn't changed, avoiding redundant JSON parsing.
6. **Thread generation counter** — `_thread_generation` prevents stale effect threads from corrupting engine state after a new effect starts.
7. **`stop_event.wait(dt)` frame pacing** — Effect loops use event waits instead of `time.sleep()`, allowing immediate interruption on stop.
8. **Throttled logging** — `log_throttled()` prevents log flooding from polling loops.
9. **Single-instance lock** — `fcntl.flock(LOCK_NB)` prevents multiple tray instances fighting over USB devices.
10. **In-place buffer reuse** — `_age_pulses_in_place()` compacts the pulse list in-place, and overlay dicts are stored on the engine instance for reuse across frames.

### Issues Found

#### 1. PyUsbTransport — no resource cleanup (Medium)

**File:** `src/core/backends/ite8291r3/usb.py`

`PyUsbTransport` opens USB device handles via `pyusb` but never explicitly closes them. There is no `close()` or `__del__` method. The kernel driver is detached (`_detach_kernel_driver_if_needed`) but never re-attached on transport disposal.

**Impact:**
- If the backend is switched or re-probed, old USB handles may leak.
- Kernel driver remains detached for the process lifetime, preventing other tools from accessing the device until the process exits.

**Fix:** Add `close()` and `__del__` to `PyUsbTransport`. Track whether the kernel driver was detached so it can be re-attached on cleanup. Add corresponding cleanup in `open_matching_transport` callers.

---

#### 2. Effect thread join timeout — abandoned threads may write stale data (Medium)

**File:** `src/core/effects/engine_support/core.py`, line 192

`_EngineCore.stop()` joins the effect thread with a 2-second timeout. If the thread is still alive after the timeout, `stop()` returns early **without** calling `stop_event.clear()`. This means the next `start_effect()` call will find `stop_event` already set, potentially interfering with the new effect's startup sequence.

The `_thread_generation` counter does protect against stale threads corrupting the `running` flag, but the uncleared `stop_event` is a latent issue.

**Impact:** After a hung thread, the next effect start may not properly initialise its `stop_event`.

**Fix:** Ensure `stop_event.clear()` is always called at the end of `stop()`, regardless of thread join outcome.

---

#### 3. Subprocess cleanup — dbus-monitor and acpi_listen become zombies (Low–Medium)

**Files:**
- `src/core/power/monitoring/login1_monitoring.py`
- `src/core/power/monitoring/acpi_monitoring.py`

Both functions spawn `subprocess.Popen` processes but never call `terminate()` or `kill()`. When `is_running()` returns `False` and the readline loop exits, the process is not explicitly cleaned up. If the daemon thread is killed or the main process exits abruptly, these subprocesses may linger as zombies.

**Impact:** Zombie processes consuming system resources; potentially blocked dbus-monitor instances preventing other tools from accessing login1.

**Fix:** Store the `Popen` process reference and call `terminate()` in a `finally` block after the read loop exits.

---

#### 4. Config not thread-safe across processes (Low)

**File:** `src/core/config/config.py`, `src/core/config/file_storage.py`

Multiple `Config()` objects can exist (tray + GUI windows). Each property setter triggers `self._save()` (atomic JSON write). The config polling thread reloads via mtime+digest heuristics. A GUI window writing config between the tray's read-merge-write cycle can lose updates.

**Impact:** Low in practice due to 100ms polling, but not formally prevented.

**Status:** Note only — not addressed in this fix pass. The atomic write pattern prevents corruption; lost updates are transient.

---

#### 5. Tray state shared across threads without formal synchronization (Low)

The `KeyRGBTray` attributes like `is_off`, `_power_forced_off` are read from polling threads and written from the main thread. Python's GIL makes simple boolean/int reads atomic, but there are no memory barrier guarantees.

**Status:** Note only — not addressed. In practice, Python's GIL provides sufficient ordering for flag-like booleans.

---

## RAM Usage Analysis

### Baseline Measurement (from 0.19.0 profiling)

| Metric | Value |
|---|---|
| VmRSS | ~108 MiB |
| PSS | ~81 MiB |
| Private_Dirty | ~62 MiB |
| Thread count | 16 |

The baseline was **flat** across repeated idle samples, ruling out active leak behavior.

### Memory Architecture

| Component | Est. Contribution | Notes |
|---|---|---|
| Python interpreter | ~25 MiB | Fixed baseline |
| Pillow (tray icon) | ~20–25 MiB | Loaded for icon rendering; significant relative to app code |
| pystray + evdev | ~5–10 MiB | Native library bindings |
| App code + config | ~5 MiB | Small; mostly dataclass/dict state |
| Effect buffers (per-key map) | ~10–20 KiB | Fixed-size dicts reused across frames; negligible |
| Pulse lists (reactive) | ~1–5 KiB | In-place compaction; already well-managed |
| Total estimated | ~55–65 MiB private | Matches Private_Dirty reading |

### RAM Optimisation Notes

1. **Pillow is the largest discretionary allocation** — if tray icons could be rendered without full Pillow, ~20 MiB could be saved. This would require a significant refactoring effort.
2. **Effect buffer reuse is already good** — `get_engine_color_map_buffer()` and `get_engine_overlay_buffer()` cache dicts on the engine instance. Pulse aging is already in-place.
3. **Config reload is efficient** — mtime+digest caching prevents unnecessary JSON re-reads.
4. **No large data structures leak** — profiles, keymaps, and color maps are bounded and short-lived in the render path.

### Potential RAM Reductions (Not Addressed in This Pass)

| Target | Est. Saving | Effort |
|---|---|---|
| Lazy Pillow import for non-tray paths | ~20 MiB | Medium — icon rendering is deeply entangled |
| Defer backend probing for known hardware | ~2–5 MiB | Low-Probe imports are already somewhat gated |
| Shared config snapshot (instead of per-window instance) | <1 MiB | Low — but adds complexity for marginal gain |
| Module-lazy import for rarely-used backends | ~1–3 MiB | Low — `ite8291r3` already lazy via registry |

---

## Changes Applied

### Fix 1: PyUsbTransport resource cleanup

- Added `close()` method to `PyUsbTransport` that:
  - Re-attaches kernel driver if it was previously detached (best-effort, logged on failure)
  - Disposes the USB device handle via `usb_util.dispose_devices()`
- Added `__del__` as a safety-net destructor that calls `close()` with a warning log if the transport was still open.
- `open_matching_transport` now tracks `_kernel_driver_detached` state on the transport for proper re-attachment.

### Fix 2: Effect thread stop_event cleanup

- `_EngineCore.stop()` now always calls `stop_event.clear()` at the end, even if the thread join timed out.
- This prevents a stale `stop_event` from interfering with the next effect start.

### Fix 3: Subprocess cleanup for power monitors

- `login1_monitoring.monitor_prepare_for_sleep()` now stores the `Popen` process and calls `process.terminate()` in a `finally` block.
- `acpi_monitoring.monitor_acpi_events()` now stores the `Popen` process and calls `process.terminate()` in a `finally` block.
- Both functions also log a debug message on cleanup for observability.

### Fix 4: USB device / backend resource lifecycle (`close()` wiring)

- Added `close()` to `KeyboardDevice` (base protocol), `KeyboardDeviceProtocol` (effects protocol), `NullKeyboard`, and `_BrightnessLoggingKeyboardProxy`.
- `Ite8291r3KeyboardDevice` now stores a reference to its `PyUsbTransport` and delegates `close()` to it.
- `Ite8291KeyboardDevice` and `Ite8910KeyboardDevice` now store a reference to their HID transport and delegate `close()`.
- `_EngineCore.close()` stops the current effect, replaces the keyboard with `NullKeyboard`, and calls `close()` on the old device.
- `_EngineCore.mark_device_unavailable()` now calls `close()` on the old keyboard before replacing it.
- `_on_quit_clicked` in the tray delegates now calls `engine.close()` after `engine.stop()`.
- All `close()` methods are idempotent and best-effort (logged on failure, never raise).

### Fix 5: Config file-locking for cross-process safety

- `file_storage.py` now uses `fcntl.flock(LOCK_SH)` for reads and `fcntl.flock(LOCK_EX)` for writes via a `config.lock` file in the config directory.
- This prevents concurrent tray and GUI processes from interleaving reads and writes, eliminating the lost-update race window between `Config.reload()` and `Config._save()`.
- Lock acquisition failures are non-fatal: if the lock cannot be acquired, the operation proceeds without locking (graceful degradation).

---

## Outstanding Items

### Reactive brightness test failures (12 tests) — FIXED

The reactive brightness test suite had 12 pre-existing test failures caused by a `ReactiveRenderState` dataclass refactoring that was not fully reflected in the tests. All four root causes have been fixed:

| Group | Tests | Fix Applied |
|---|---|---|
| A | 5 tests in `test_reactive_effects_math_unit.py` | Updated to use `ensure_reactive_state(engine)` and read values from the dataclass |
| B | 2 tests in `test_reactive_render_brightness_policy_unit.py` | Updated import from `_MAX_BRIGHTNESS_STEP_PER_FRAME` to `MAX_BRIGHTNESS_STEP_PER_FRAME` in `_constants.py` |
| C | 2 tests in `test_reactive_render_brightness_policy_unit.py` | Rewrote `clear_transition_state` tests to verify the dataclass state directly instead of testing `__setattr__` on the engine |
| D | 3 tests in `test_reactive_pulse_brightness_unit.py` | Replaced `_reactive_post_restore_*` attributes with `ReactiveRestorePhase.DAMPING` and `_reactive_restore_damp_until` via `ensure_reactive_state()` |

---

## Validation Commands

```bash
# Targeted unit tests for the changed modules
python -m pytest tests/core/effects/engine/test_effects_engine_stop_unit.py -v
python -m pytest tests/core/power/monitoring/test_login1_monitoring_unit.py -v
python -m pytest tests/core/power/monitoring/test_acpi_monitoring_unit.py -v
python -m pytest tests/core/backends/ -v
python -m pytest tests/core/config/test_config_file_storage_unit.py -v

# Exception-transparency validation
python -m buildpython --run-steps=19
```