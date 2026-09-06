"""Pulse visual scaling for reactive rendering."""

from __future__ import annotations

from operator import attrgetter
from typing import TYPE_CHECKING

from . import _render_brightness_support as _brightness_support
from ._render_brightness_debug import log_pulse_visual_scale_change
from ._render_post_restore import post_restore_visual_damp

if TYPE_CHECKING:
    from keyrgb.core.effects.engine import EffectsEngine


_INT_COERCION_ERRORS = (TypeError, ValueError)


def pulse_brightness_scale_factor(engine: EffectsEngine) -> float:
    """Compute scaling factor to keep pulses at their target brightness.

    This is expressed relative to the resolved hardware brightness used for
    rendering. Uniform-only backends may transiently raise the hardware
    brightness to make bright pulses possible over a dim backdrop; per-key
    backends keep hardware brightness fixed and rely on per-key color contrast.
    For per-key hardware the reactive slider should therefore control the pulse
    color intensity directly across the full 0..50 range. Any extra suppression
    must stay scoped to explicit post-restore recovery windows (any steady
    brightness) so normal typing outside those windows keeps the configured
    reactive level.
    """

    # These helpers remain in render.py as part of its tested facade. Importing
    # lazily keeps the facade re-export from creating an import cycle.
    from . import render as render_mod

    base, eff, hw = render_mod._resolve_brightness(engine)
    visual_mode = render_mod.reactive_visual_mode(engine, default="vivid")

    if render_mod.has_per_key(engine):
        pulse_scale = render_mod._apply_reactive_pulse_visual_curve(
            float(max(0, min(50, int(eff)))) / 50.0,
            visual_mode=visual_mode,
        )
        target_hw = _steady_target_hw_brightness(engine, base=base)
        visual_hw = min(int(hw), int(target_hw))
        if visual_hw <= 0:
            log_pulse_visual_scale_change(
                engine,
                logger=render_mod.logger,
                base=base,
                eff=eff,
                hw=hw,
                target_hw=target_hw,
                visual_hw=visual_hw,
                pulse_scale=0.0,
                contrast_ratio=0.0,
                contrast_compression=0.0,
                very_dim_curve=False,
                post_restore_holdoff_remaining_s=0.0,
                post_restore_damp=1.0,
            )
            return 0.0

        # Post-restore damp must apply at any steady brightness (not only the
        # very-dim curve). Nesting damp under visual_hw < 10 left normal bases
        # (e.g. 20) undamped on typing-wake after long idle off — deck-wide flash.
        post_restore_damp, post_restore_holdoff_remaining_s = post_restore_visual_damp(engine)
        very_dim_curve = visual_hw < 10
        release_scale = _post_fade_reactive_release_scale(
            engine,
            post_restore_damp=post_restore_damp,
            visual_mode=visual_mode,
        )

        if eff <= visual_hw:
            final_scale = float(pulse_scale) * float(post_restore_damp) if release_scale is None else release_scale
            log_pulse_visual_scale_change(
                engine,
                logger=render_mod.logger,
                base=base,
                eff=eff,
                hw=hw,
                target_hw=target_hw,
                visual_hw=visual_hw,
                pulse_scale=final_scale,
                contrast_ratio=1.0,
                contrast_compression=1.0,
                very_dim_curve=very_dim_curve,
                post_restore_holdoff_remaining_s=post_restore_holdoff_remaining_s,
                post_restore_damp=post_restore_damp,
            )
            return final_scale

        baseline_scale = float(visual_hw) / 50.0
        contrast_ratio = float(visual_hw) / float(eff)
        contrast_compression = 1.0
        # damp=1.0 outside restore windows => final_scale == pulse_scale.
        if pulse_scale > baseline_scale:
            final_scale = baseline_scale + ((pulse_scale - baseline_scale) * float(post_restore_damp))
        else:
            final_scale = float(pulse_scale) * float(post_restore_damp)
        if release_scale is not None:
            final_scale = release_scale
        log_pulse_visual_scale_change(
            engine,
            logger=render_mod.logger,
            base=base,
            eff=eff,
            hw=hw,
            target_hw=target_hw,
            visual_hw=visual_hw,
            pulse_scale=final_scale,
            contrast_ratio=contrast_ratio,
            contrast_compression=contrast_compression,
            very_dim_curve=very_dim_curve,
            post_restore_holdoff_remaining_s=post_restore_holdoff_remaining_s,
            post_restore_damp=post_restore_damp,
        )
        return final_scale

    if hw <= 0:
        return 0.0

    if eff >= hw:
        return 1.0

    return render_mod._apply_reactive_pulse_visual_curve(float(eff) / float(hw), visual_mode=visual_mode)


def _post_fade_reactive_release_scale(
    engine: EffectsEngine,
    *,
    post_restore_damp: float,
    visual_mode: str,
) -> float | None:
    """Blend across the idle-restore effect release without a baseline jump."""

    # Resolve through render.time so tests can patch the established facade
    # seam, even though this implementation lives in a helper module.
    from . import render as render_mod

    raw_state = _brightness_support.read_engine_attr(
        engine,
        "_reactive_state",
        missing_default=None,
        error_default=None,
        logger=render_mod.logger,
    )
    if not isinstance(raw_state, _brightness_support.ReactiveRenderState):
        return None
    state = raw_state

    reactive_lock = getattr(engine, "reactive_lock", None)
    raw_from: object
    raw_to: object
    started_at: object
    duration_s: object
    if reactive_lock is not None:
        raw_from, raw_to, started_at, duration_s = _brightness_support.read_transition_atomic(
            state,
            reactive_lock,
        )
    else:
        raw_from = _brightness_support.read_engine_attr(
            engine,
            "_reactive_transition_from_brightness",
            missing_default=None,
            error_default=None,
            logger=render_mod.logger,
        )
        raw_to = _brightness_support.read_engine_attr(
            engine,
            "_reactive_transition_to_brightness",
            missing_default=None,
            error_default=None,
            logger=render_mod.logger,
        )
        started_at = _brightness_support.read_engine_attr(
            engine,
            "_reactive_transition_started_at",
            missing_default=None,
            error_default=None,
            logger=render_mod.logger,
        )
        duration_s = _brightness_support.read_engine_attr(
            engine,
            "_reactive_transition_duration_s",
            missing_default=None,
            error_default=None,
            logger=render_mod.logger,
        )
    transition_from = _brightness_support.coerce_brightness(raw_from, default=None)
    transition_to = _brightness_support.coerce_brightness(raw_to, default=None)
    if transition_from is None or transition_to is None or transition_to <= transition_from:
        return None
    started = _brightness_support.coerce_float(started_at, default=None)
    duration = _brightness_support.coerce_float(duration_s, default=None)
    if started is None or duration is None or duration <= 0.0:
        return None

    raw_global = _brightness_support.read_engine_attr(
        engine,
        "brightness",
        missing_default=None,
        error_default=None,
        logger=render_mod.logger,
    )
    global_hw = _brightness_support.coerce_brightness(raw_global, default=None)
    if global_hw != transition_from:
        return None

    release_progress = max(0.0, min(1.0, (float(render_mod.time.monotonic()) - started) / duration))
    raw_effect_target = _brightness_support.read_engine_attr(
        engine,
        "reactive_brightness",
        missing_default=global_hw,
        error_default=global_hw,
        logger=render_mod.logger,
    )
    effect_target = _brightness_support.coerce_brightness(raw_effect_target, default=global_hw)
    if effect_target is None:
        effect_target = global_hw
    base_target = 0
    per_key_colors = _brightness_support.read_engine_attr(
        engine,
        "per_key_colors",
        missing_default=None,
        error_default=None,
        logger=render_mod.logger,
    )
    if per_key_colors:
        raw_base_target = _brightness_support.read_engine_attr(
            engine,
            "per_key_brightness",
            missing_default=0,
            error_default=0,
            logger=render_mod.logger,
        )
        base_target = _brightness_support.coerce_brightness(raw_base_target, default=0) or 0

    start_effect = min(effect_target, transition_from)
    target_visual_hw = max(global_hw, base_target)
    start_pulse_scale = render_mod._apply_reactive_pulse_visual_curve(
        float(start_effect) / 50.0,
        visual_mode=visual_mode,
    )
    target_pulse_scale = render_mod._apply_reactive_pulse_visual_curve(
        float(effect_target) / 50.0,
        visual_mode=visual_mode,
    )
    start_scale = float(start_pulse_scale) * float(post_restore_damp)
    if effect_target <= target_visual_hw:
        target_scale = float(target_pulse_scale) * float(post_restore_damp)
    else:
        baseline_scale = float(target_visual_hw) / 50.0
        target_scale = baseline_scale + ((target_pulse_scale - baseline_scale) * float(post_restore_damp))
    return start_scale + ((target_scale - start_scale) * release_progress)


def _steady_target_hw_brightness(engine: EffectsEngine, *, base: int) -> int:
    try:
        raw_global_hw = attrgetter("brightness")(engine)
    except AttributeError:
        raw_global_hw = 25
    try:
        coerced = _brightness_support.coerce_int(raw_global_hw, default=25)
        global_hw = 25 if coerced is None else coerced
    except _INT_COERCION_ERRORS:
        global_hw = 25
    global_hw = max(0, min(50, global_hw))
    return max(int(base), global_hw)
