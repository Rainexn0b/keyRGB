# Reactive Brightness Invariants

This note documents the renderer rules that keep reactive typing stable on ITE
per-key keyboards while preserving the uniform-backend fallback.

## Why This Exists

Reactive typing regressions in this codebase have clustered around one boundary:
the distinction between per-key pulse content and whole-keyboard hardware
brightness. When those two responsibilities blur, the result is visible flicker.

The tests in `tests/core/test_reactive_render_brightness_cap_unit.py`,
`tests/core/test_reactive_pulse_brightness_unit.py`, and
`tests/tray/test_brightness_stability_guard_unit.py` lock down the
invariants below.

## Invariants

1. Idle reactive hardware brightness follows the active profile brightness.

On per-key hardware, `reactive_brightness` is a pulse target, not the steady
state deck brightness. Idle hardware brightness should resolve to the profile
baseline (`engine.brightness`, or `max(engine.brightness, per_key_brightness)`
when a per-key backdrop is active).

2. Per-key reactive pulses must not raise whole-keyboard hardware brightness.

Per-key pulse visibility comes from the per-key color map itself. Sending a
global `SET_BRIGHTNESS` bump for every keypress makes the entire keyboard flash,
which reads as unrelated brightness flicker instead of a local ripple.

3. Uniform-only backends may still use pulse-time hardware lifts.

If the backend cannot render per-key data, there is no local pulse content to
modulate. In that fallback path, a short hardware-brightness lift remains valid
so reactive typing is still perceptible.

4. Temp-dim is authoritative.

When screen-dim sync is active, reactive pulses must not exceed the dim target.
The render loop may animate toward the dim or restore target, but the active
temp-dim brightness remains the ceiling for hardware writes.

5. `SET_BRIGHTNESS` is a frame commit, not just a cached property update.

On the ITE 8291 path, sending `SET_BRIGHTNESS` before row data can leave the
visual frame stale until the next commit. Per-key renders therefore send row
data first and only then send `SET_BRIGHTNESS` when the hardware brightness
actually changed.

6. First-frame startup and post-stop behavior must ramp from the intended base.

After `stop()`, `_last_rendered_brightness` and `_last_hw_mode_brightness` are
reset so the next render loop starts from a known dark state and reinitializes
user mode cleanly. This prevents stale-brightness flashes during restart,
restore, or wake flows.

## Test Strategy

The current regression suite intentionally splits behavior by backend class:

- Per-key render tests prove that reactive keypresses do not trigger global
  hardware-brightness bumps.
- Uniform render tests prove that the visibility fallback still works where no
  per-key output exists.
- Guard and dim tests prove that the no-flicker pulse rules do not regress the
  earlier dim, restore, and wake fixes.

If reactive flicker returns, inspect `src/core/effects/reactive/render.py`
first. In practice, most regressions come from changing `_resolve_brightness()`
or the ordering of `set_key_colors`, `set_color`, and `set_brightness`.