from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
)
from src.core.effects.transitions import avoid_full_black
from src.core.utils.logging_utils import log_throttled
from src.core.utils.exceptions import is_device_disconnected

logger = logging.getLogger(__name__)

# Maximum brightness change per render frame before the stability guard
# clamps. Prevents single-frame jumps (e.g. 3 -> 50) caused by race
# conditions between concurrent brightness writers.
_MAX_BRIGHTNESS_STEP_PER_FRAME: int = 8

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def mix(a: Color, b: Color, t: float) -> Color:
    tt = clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * tt)),
        int(round(a[1] + (b[1] - a[1]) * tt)),
        int(round(a[2] + (b[2] - a[2]) * tt)),
    )


def scale(rgb: Color, s: float) -> Color:
    ss = clamp01(s)
    return (int(round(rgb[0] * ss)), int(round(rgb[1] * ss)), int(round(rgb[2] * ss)))


def _resolve_reactive_transition_brightness(engine: "EffectsEngine") -> Optional[tuple[int, bool]]:
    """Return the current transition brightness for reactive temp-dim flows.

    The idle-power poller updates engine brightness atomically under kb_lock,
    then the render loop interpolates toward the new target over a short time
    window so dim/restore feels deliberate without blocking the render thread.
    """

    try:
        start = getattr(engine, "_reactive_transition_from_brightness", None)
        end = getattr(engine, "_reactive_transition_to_brightness", None)
        started_at = getattr(engine, "_reactive_transition_started_at", None)
        duration_s = getattr(engine, "_reactive_transition_duration_s", None)
    except Exception:
        return None

    if start is None or end is None or started_at is None or duration_s is None:
        return None

    try:
        start_i = max(0, min(50, int(start)))
        end_i = max(0, min(50, int(end)))
        duration = max(0.0, float(duration_s))
        started = float(started_at)
    except Exception:
        return None

    if duration <= 0.0 or start_i == end_i:
        try:
            engine._reactive_transition_from_brightness = None
            engine._reactive_transition_to_brightness = None
            engine._reactive_transition_started_at = None
            engine._reactive_transition_duration_s = None
        except Exception:
            pass
        return end_i, bool(end_i >= start_i)

    elapsed = max(0.0, float(time.monotonic()) - started)
    if elapsed >= duration:
        try:
            engine._reactive_transition_from_brightness = None
            engine._reactive_transition_to_brightness = None
            engine._reactive_transition_started_at = None
            engine._reactive_transition_duration_s = None
        except Exception:
            pass
        return end_i, bool(end_i >= start_i)

    t = clamp01(elapsed / duration)
    current = int(round(start_i + (end_i - start_i) * t))
    return current, bool(end_i >= start_i)


def _resolve_brightness(engine: "EffectsEngine") -> Tuple[int, int, int]:
    """Resolve brightness levels for mixed-content rendering.

    Returns (base_hw, effect_hw, hw_brightness).

    Brightness resolution rules:
    1. Read all brightness inputs from the engine.
    2. When dim-temp is active, lock HW brightness to ``engine.brightness``
       (the policy-set dim target) — reactive pulses must NOT raise it.
     3. Otherwise idle hw = max(global_hw, base).  ``reactive_brightness`` (eff)
         does NOT raise the hardware brightness at steady state, so the keyboard
         sits at the expected profile level when idle.
     4. On uniform-only backends, a reactive pulse may transiently lift the
         hardware brightness between the idle hw and ``eff`` scaled by the live
         pulse mix (0..1). Per-key backends keep hw fixed at the profile level
         so a keypress does not cause a whole-keyboard brightness flicker.
     5. Apply ``_hw_brightness_cap`` as a hard ceiling in all cases.
     6. Apply per-frame stability guard: clamp the change from the previous
       rendered brightness to ``_MAX_BRIGHTNESS_STEP_PER_FRAME`` to prevent
       single-frame jumps caused by concurrent writers racing.
    """
    # Pulse/highlight target brightness for reactive effects.
    try:
        eff = int(getattr(engine, "reactive_brightness", getattr(engine, "brightness", 25)) or 0)
    except Exception:
        eff = 25
    eff = max(0, min(50, eff))

    # Profile/policy-selected hardware brightness.
    try:
        global_hw = int(getattr(engine, "brightness", 25) or 0)
    except Exception:
        global_hw = 25
    global_hw = max(0, min(50, global_hw))

    # Per-key backdrop brightness (only meaningful when a per-key map is loaded).
    base = 0
    try:
        if getattr(engine, "per_key_colors", None):
            base = int(getattr(engine, "per_key_brightness", 0) or 0)
    except Exception:
        pass
    base = max(0, min(50, base))

    transition = _resolve_reactive_transition_brightness(engine)
    if transition is not None:
        transition_brightness, rising = transition
        eff = min(eff, transition_brightness)
        if rising:
            global_hw = min(global_hw, transition_brightness)
            base = min(base, transition_brightness)
        else:
            global_hw = max(global_hw, transition_brightness)
            base = max(base, transition_brightness)

    # --- dim-temp guard -------------------------------------------------------
    # During screen-dim sync, we MUST NOT raise HW brightness above the policy
    # target or we'll fight dim/restore, causing flicker.
    dim_temp_active = bool(getattr(engine, "_dim_temp_active", False))

    per_key_hw = bool(getattr(getattr(engine, "kb", None), "set_key_colors", None))

    pulse_mix = 0.0
    allow_pulse_hw_lift = False
    if dim_temp_active:
        # Lock to the policy-set dim target.
        hw = global_hw
        idle_hw = hw
    else:
        try:
            pulse_mix = float(getattr(engine, "_reactive_active_pulse_mix", 0.0) or 0.0)
        except Exception:
            pulse_mix = 0.0
        pulse_mix = clamp01(pulse_mix)

        # The hardware brightness tracks the profile brightness (global_hw) and
        # the per-key backdrop brightness (base), but NOT reactive_brightness
        # (eff).  Keeping hw = max(global_hw, base) means the keyboard sits at
        # engine.brightness at idle, matching the user's slider expectation.
        #
        # For per-key hardware, pulse visibility comes from the per-key color
        # map itself. Raising the hardware brightness on every keypress makes
        # the entire keyboard flash, independent of where the pulse is.
        # Restrict hardware-level pulse lifts to uniform-only backends where
        # there is no per-key content to modulate.
        #
        # During a restore transition, global_hw is driven by the transition
        # (min(engine.brightness, transition_val) for rising), so hw still
        # follows the transition ramp smoothly — eff doesn't need to
        # participate.
        hw = max(global_hw, base)
        idle_hw = hw
        allow_pulse_hw_lift = (not per_key_hw) and pulse_mix > 0.0 and eff > hw
        if allow_pulse_hw_lift:
            pulse_hw = int(round(float(hw) + (float(eff - hw) * pulse_mix)))
            hw = max(hw, pulse_hw)

    # --- hard ceiling from idle-power policy ----------------------------------
    policy_cap: Optional[int] = None
    try:
        raw_cap = getattr(engine, "_hw_brightness_cap", None)
        if raw_cap is not None:
            policy_cap = max(0, min(50, int(raw_cap)))
    except Exception:
        pass

    if policy_cap is not None:
        hw = min(hw, policy_cap)

    hw = max(0, min(50, hw))

    # --- per-frame stability guard --------------------------------------------
    # Prevent single-frame brightness jumps caused by concurrent writers (e.g.
    # idle-power clearing the cap one frame before brightness is restored).
    #
    # When _last_rendered_brightness is None (first frame after a stop/restart),
    # treat it as 0 so the guard ramps up naturally from dark instead of
    # bypassing the guard and jumping straight to target brightness.  This
    # ensures that a wake-from-off restore (where brightness_override=1 is
    # intended to produce a fade-in) doesn't immediately write at full
    # brightness on the first frame.
    #
    # Exception: when temp-dim is active and brightness is falling, bypass the
    # guard entirely.  The guard's slow step-ramp (−8 per frame ≈ 200 ms to
    # reach dim target) causes 6 separate 34 ms windows where new frames are
    # displayed at the previous higher brightness before each SET_BRIGHTNESS
    # fires — visible as a staircase flash.  With dim_temp_active the target
    # brightness is an authoritative policy value, not a racing concurrent
    # write, so the guard's race-protection purpose does not apply.  Jumping
    # directly to the dim target means only ONE such window (the transfer of
    # the first dim frame while HW is still at the old brightness), which is
    # much less perceptible than the 6-step staircase.
    try:
        prev = getattr(engine, "_last_rendered_brightness", None)
        prev_i = int(prev) if prev is not None else 0
        delta = hw - prev_i
        guard_active = abs(delta) > _MAX_BRIGHTNESS_STEP_PER_FRAME
        # Skip the guard for authoritative policy dims and intentional pulse
        # rises. In both cases the brightness jump is deliberate rather than a
        # concurrent-writer race.
        if guard_active and dim_temp_active and delta < 0:
            guard_active = False
        if guard_active and allow_pulse_hw_lift and delta > 0:
            guard_active = False
        if guard_active and (not per_key_hw) and delta < 0 and prev_i > idle_hw and eff > idle_hw:
            guard_active = False
        if guard_active:
            hw = prev_i + (_MAX_BRIGHTNESS_STEP_PER_FRAME if delta > 0 else -_MAX_BRIGHTNESS_STEP_PER_FRAME)
            hw = max(0, min(50, hw))
            if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
                logger.info(
                    "brightness_guard: clamped %s->%s (prev=%s, cap=%s, dim=%s)",
                    prev_i + delta, hw, prev_i, policy_cap, dim_temp_active,
                )
    except Exception:
        pass

    return base, eff, hw


def backdrop_brightness_scale_factor(engine: "EffectsEngine", *, effect_brightness_hw: int) -> float:
    """Compute scaling factor to keep the backdrop at its target brightness.

    If the global hardware brightness is driven higher (by the effect brightness),
    we scale the backdrop down.
    """
    base, _, hw = _resolve_brightness(engine)

    if hw <= 0:
        return 0.0

    if base >= hw:
        return 1.0

    return float(base) / float(hw)


def pulse_brightness_scale_factor(engine: "EffectsEngine") -> float:
    """Compute scaling factor to keep pulses at their target brightness.

    This is expressed relative to the resolved hardware brightness used for
    rendering. Uniform-only backends may transiently raise the hardware
    brightness to make bright pulses possible over a dim backdrop; per-key
    backends keep hardware brightness fixed and rely on per-key color contrast.
    """

    _, eff, hw = _resolve_brightness(engine)

    if hw <= 0:
        return 0.0

    if eff >= hw:
        return 1.0

    return float(eff) / float(hw)


def apply_backdrop_brightness_scale(color_map: Dict[Key, Color], *, factor: float) -> Dict[Key, Color]:
    """Return a scaled copy of a per-key base map."""

    f = float(factor)
    if f >= 0.999:
        return dict(color_map)
    if f <= 0.0:
        return {k: (0, 0, 0) for k in color_map.keys()}
    return {k: scale(rgb, f) for k, rgb in color_map.items()}


def frame_dt_s() -> float:
    return 1.0 / 60.0


def pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Matches the quadratic mapping used by the SW loops: speed=10 is much faster.
    """

    try:
        s = int(getattr(engine, "speed", 4) or 0)
    except Exception:
        s = 4

    s = max(0, min(10, s))
    t = float(s) / 10.0
    t = t * t

    min_factor = float(min_factor)
    max_factor = float(max_factor)
    if min_factor == 0.8 and max_factor == 2.2:
        min_factor = 0.25
        max_factor = 10.0

    return float(min_factor + (max_factor - min_factor) * t)


def has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(engine.kb, "set_key_colors", None))


def base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (
        int(base_color_src[0]),
        int(base_color_src[1]),
        int(base_color_src[2]),
    )

    per_key = getattr(engine, "per_key_colors", None) or None
    if not per_key:
        return {(r, c): base_color for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    full = build_full_color_grid(
        base_color=base_color,
        per_key_colors=per_key,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )

    out: Dict[Key, Color] = {}
    for (r, c), rgb in full.items():
        out[(r, c)] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return out


def _apply_hw_brightness(engine: "EffectsEngine", brightness_hw: int) -> None:
    """Set hardware brightness, avoiding a full mode reinit when possible.

    The ITE controller's ``enable_user_mode`` sends a ``SET_EFFECT`` command
    (cmd 8) which reinitialises the LED controller mode.  On some firmware
    this causes a brief visible flash.  Since the reactive render loop calls
    this every frame (~60 fps), flashing accumulates during brightness ramps
    (dim→restore) and produces a noticeable strobe.

    Instead, we use ``SET_EFFECT`` only for the *first* frame after a
    stop/restart (to initialise user mode) and the lighter
    ``SET_BRIGHTNESS`` (cmd 9) for subsequent brightness changes.  When
    brightness hasn't changed at all, we skip the USB transfer entirely.
    """

    prev = getattr(engine, "_last_hw_mode_brightness", None)

    if prev is None:
        # First frame after stop/restart — full mode init required.
        enable_user_mode_once(
            kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw)
        )
        engine._last_hw_mode_brightness = int(brightness_hw)
        return

    if int(prev) == int(brightness_hw):
        # Brightness unchanged — skip the USB transfer entirely.
        return

    # Brightness changed — use the lightweight SET_BRIGHTNESS command.
    try:
        engine.kb.set_brightness(int(brightness_hw))
    except Exception:
        # Fallback: full mode reinit if set_brightness is missing or failed.
        enable_user_mode_once(
            kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw)
        )
    engine._last_hw_mode_brightness = int(brightness_hw)


def render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    # Determine proper hardware brightness scaling. Keep resolution under the
    # same lock used by device I/O so a tray-initiated dim/restore can't race
    # a frame and produce a one-frame stale brightness write.

    if has_per_key(engine):
        try:
            with engine.kb_lock:
                _, _, brightness_hw = _resolve_brightness(engine)
                engine._last_rendered_brightness = brightness_hw

                # If user mode has NOT been initialised yet (should be rare
                # due to _start_sw_effect priming it), send SET_EFFECT first
                # so the controller accepts per-key data.
                need_mode_init = getattr(engine, "_last_hw_mode_brightness", None) is None
                if need_mode_init:
                    _apply_hw_brightness(engine, brightness_hw)

                try:
                    engine.kb.set_key_colors(color_map, brightness=int(brightness_hw), enable_user_mode=False)
                except Exception as exc:
                    if is_device_disconnected(exc):
                        try:
                            engine.mark_device_unavailable()
                        except Exception:
                            pass
                        return
                    raise

                # Send SET_BRIGHTNESS *after* per-key data.  The ITE 8291
                # firmware treats SET_BRIGHTNESS as the commit/refresh
                # signal for the current frame: sending it before row data
                # updates the internal brightness register but does not
                # visually apply until the next commit, so the display stays
                # at the old brightness regardless of what we sent.  Always
                # sending SET_BRIGHTNESS after the row data ensures the
                # new brightness takes effect simultaneously with the new
                # frame contents.
                if not need_mode_init:
                    _apply_hw_brightness(engine, brightness_hw)
                return
        except Exception as exc:
            log_throttled(
                logger,
                "effects.render.per_key_failed",
                interval_s=30,
                level=logging.WARNING,
                msg="Per-key render failed; falling back to uniform",
                exc=exc,
            )

    if not color_map:
        rgb = (0, 0, 0)
    else:
        rs = sum(c[0] for c in color_map.values())
        gs = sum(c[1] for c in color_map.values())
        bs = sum(c[2] for c in color_map.values())
        n = max(1, len(color_map))
        rgb = (int(rs / n), int(gs / n), int(bs / n))

    with engine.kb_lock:
        _, _, brightness_hw = _resolve_brightness(engine)
        engine._last_rendered_brightness = brightness_hw
        r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(brightness_hw))

        need_mode_init = getattr(engine, "_last_hw_mode_brightness", None) is None
        if need_mode_init:
            _apply_hw_brightness(engine, brightness_hw)

        engine.kb.set_color((r, g, b), brightness=int(brightness_hw))

        if not need_mode_init:
            _apply_hw_brightness(engine, brightness_hw)
