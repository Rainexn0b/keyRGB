from __future__ import annotations

import logging
import os


def apply_brightness_step_guard(
    *,
    hw: int,
    prev_i: int | None,
    max_step_per_frame: int,
    dim_temp_active: bool,
    allow_pulse_hw_lift: bool,
    per_key_hw: bool,
    idle_hw: int,
    eff: int,
    policy_cap: int | None,
    logger: logging.Logger,
) -> int:
    """Clamp abrupt frame-to-frame brightness jumps unless policy allows bypass."""

    if prev_i is None:
        return hw

    delta = hw - prev_i
    guard_active = abs(delta) > max_step_per_frame
    if guard_active and dim_temp_active and delta < 0:
        guard_active = False
    if guard_active and allow_pulse_hw_lift and delta > 0:
        guard_active = False
    if guard_active and (not per_key_hw) and delta < 0 and prev_i > idle_hw and eff > idle_hw:
        guard_active = False

    if not guard_active:
        return hw

    guarded = prev_i + (max_step_per_frame if delta > 0 else -max_step_per_frame)
    guarded = max(0, min(50, guarded))
    if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
        logger.info(
            "brightness_guard: clamped %s->%s (prev=%s, cap=%s, dim=%s)",
            prev_i + delta,
            guarded,
            prev_i,
            policy_cap,
            dim_temp_active,
        )
    return guarded