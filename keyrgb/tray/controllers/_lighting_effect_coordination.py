"""Internal coordination helpers for lighting effect startup and transitions.

This module encapsulates the non-public coordination logic extracted from
lighting_controller.py to reduce file size while preserving the stable
start_current_effect() public facade.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from operator import attrgetter

from keyrgb.core.backends.base import normalize_backend_capabilities
from keyrgb.core.effects.reactive import _reactive_transition_atomic, _render_brightness_support as _reactive_support
from keyrgb.core.lighting_layers import resolve_render_effect
from keyrgb.tray.idle_power_state import read_idle_power_state_bool_field
from keyrgb.tray.protocols import LightingTrayProtocol

from ._lighting_effect_engine_state import prepare_effect_engine_state  # noqa: F401

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _FadeRampPlan:
    """Plan for how to apply brightness fade ramps to an effect starting."""

    will_fade: bool
    is_loop_effect: bool
    apply_to_hardware: bool


def _seed_post_fade_reactive_release(
    tray: LightingTrayProtocol,
    *,
    from_brightness: int,
    duration_s: float,
) -> None:
    """Release reactive/base brightness smoothly after an idle soft-on ramp."""

    engine = tray.engine
    try:
        base_release_target = int(from_brightness)
        if getattr(engine, "per_key_colors", None):
            base_release_target = int(getattr(engine, "per_key_brightness", from_brightness))
        release_target = max(
            int(from_brightness),
            int(getattr(engine, "reactive_brightness", from_brightness)),
            base_release_target,
        )
        if release_target <= int(from_brightness):
            return
        started_at = float(time.monotonic())
        duration = max(0.0, float(duration_s))
        reactive_lock = getattr(engine, "reactive_lock", None)
        if reactive_lock is not None:
            _reactive_transition_atomic.seed_transition_atomic(
                _reactive_support.ensure_reactive_state(engine),
                reactive_lock,
                from_brightness=int(from_brightness),
                to_brightness=int(release_target),
                started_at=started_at,
                duration_s=duration,
            )
        else:
            _reactive_support.set_engine_attr(
                engine,
                "_reactive_transition_from_brightness",
                int(from_brightness),
            )
            _reactive_support.set_engine_attr(
                engine,
                "_reactive_transition_to_brightness",
                int(release_target),
            )
            _reactive_support.set_engine_attr(engine, "_reactive_transition_started_at", started_at)
            _reactive_support.set_engine_attr(engine, "_reactive_transition_duration_s", duration)
    except (AttributeError, RuntimeError, TypeError, ValueError, OverflowError) as exc:
        logger.warning("Failed to seed post-fade reactive release", exc_info=exc)


def _effect_generation(engine: object) -> int | None:
    try:
        return int(attrgetter("_thread_generation")(engine))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class _StartCurrentEffectPlan:
    """Classification of the effect being started."""

    effect: str
    is_perkey_mode: bool
    is_none_mode: bool
    is_loop_effect: bool
    restore_secondary_targets: bool


@dataclass(frozen=True)
class _StartCurrentEffectPolicy:
    """Resolved start-current-effect policy before side effects run."""

    effect: str
    persist_effect: str | None
    target_brightness: int
    start_brightness: int
    start_plan: _StartCurrentEffectPlan


def _coerce_brightness_override(brightness_override: object, *, default: int) -> int:
    """Coerce brightness override to valid range [0, 50]; return default on error."""
    try:
        value = int(brightness_override)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0, min(50, value))


def _plan_effect_fade_ramp(
    *,
    effect: str,
    fade_in: bool,
    start_brightness: int,
    target_brightness: int,
    is_software_effect_fn: Callable[[str], bool],
    is_reactive_effect_fn: Callable[[str], bool],
) -> _FadeRampPlan:
    """Classify the fade ramp strategy for an effect."""
    will_fade = bool(fade_in and target_brightness > start_brightness and target_brightness > 0)
    is_loop_effect = bool(is_software_effect_fn(effect) or is_reactive_effect_fn(effect))
    return _FadeRampPlan(
        will_fade=will_fade,
        is_loop_effect=is_loop_effect,
        apply_to_hardware=not is_loop_effect,
    )


def _classify_start_current_effect(
    tray: LightingTrayProtocol,
    *,
    effect: str,
    is_software_effect_fn: Callable[[str], bool],
    is_reactive_effect_fn: Callable[[str], bool],
    software_effect_target_routes_aux_devices_fn: Callable[[LightingTrayProtocol], bool],
) -> _StartCurrentEffectPlan:
    """Classify the effect being started."""
    is_perkey_mode = effect == "perkey"
    is_none_mode = effect == "none"
    is_loop_effect = bool(is_software_effect_fn(effect) or is_reactive_effect_fn(effect))
    restore_secondary_targets = bool(software_effect_target_routes_aux_devices_fn(tray))
    return _StartCurrentEffectPlan(
        effect=effect,
        is_perkey_mode=is_perkey_mode,
        is_none_mode=is_none_mode,
        is_loop_effect=is_loop_effect,
        restore_secondary_targets=restore_secondary_targets,
    )


def _resolve_start_current_effect_policy(
    tray: LightingTrayProtocol,
    *,
    brightness_override: int | None,
    safe_int_attr_fn: Callable[..., int],
    safe_str_attr_fn: Callable[..., str],
    resolve_effect_name_for_backend_fn: Callable[[str, object | None], str],
    coerce_brightness_override_fn: Callable[[object], int],
    classify_start_current_effect_fn: Callable[[LightingTrayProtocol, str], _StartCurrentEffectPlan],
) -> _StartCurrentEffectPolicy:
    """Resolve policy inputs for start_current_effect without executing engine I/O."""

    target_brightness = safe_int_attr_fn(tray.config, "brightness", default=0)
    start_brightness = target_brightness
    if brightness_override is not None:
        start_brightness = coerce_brightness_override_fn(brightness_override)

    raw_effect = safe_str_attr_fn(tray.config, "effect", default="none") or "none"
    backend = getattr(tray, "backend", None)
    selected_effect = resolve_effect_name_for_backend_fn(raw_effect, backend)
    caps = normalize_backend_capabilities(getattr(tray, "backend_caps", None))
    if selected_effect == "perkey" and not caps.per_key:
        selected_effect = "none"
    effect = resolve_render_effect(
        selected_effect=selected_effect,
        per_key_colors=getattr(tray.config, "per_key_colors", None),
        resolve_effect_name_fn=lambda effect_name: resolve_effect_name_for_backend_fn(effect_name, backend),
    )
    if effect == "perkey" and not caps.per_key:
        effect = "none"
    persist_effect = selected_effect if selected_effect != raw_effect else None
    start_plan = classify_start_current_effect_fn(tray, effect)

    return _StartCurrentEffectPolicy(
        effect=effect,
        persist_effect=persist_effect,
        target_brightness=target_brightness,
        start_brightness=start_brightness,
        start_plan=start_plan,
    )


def _run_static_effect_mode(
    tray: LightingTrayProtocol,
    *,
    apply_mode: Callable[..., None],
    start_brightness: int,
    target_brightness: int,
    fade_in: bool,
    fade_in_duration_s: float,
    restore_secondary_targets: bool,
    restore_secondary_software_targets_fn: Callable[[LightingTrayProtocol], None],
) -> None:
    """Run a static effect mode (perkey or none) with optional fade."""
    apply_mode(tray, brightness_override=start_brightness)
    if restore_secondary_targets:
        restore_secondary_software_targets_fn(tray)
    if fade_in and target_brightness > start_brightness and target_brightness > 0:
        tray.engine.set_brightness(
            target_brightness,
            apply_to_hardware=True,
            fade=True,
            fade_duration_s=float(fade_in_duration_s),
        )


def _apply_effect_fade_ramp(
    tray: LightingTrayProtocol,
    *,
    plan: _FadeRampPlan,
    start_brightness: int,
    target_brightness: int,
    fade_in_duration_s: float,
) -> None:
    """Apply the planned brightness fade ramp, preserving reactive/per-key state."""
    if not plan.will_fade:
        return

    use_loop_effect_ramp = read_idle_power_state_bool_field(
        tray,
        attr_name="_idle_restore_loop_effect_ramp",
        state_name="idle_restore_loop_effect_ramp",
        default=False,
    )

    if plan.is_loop_effect and use_loop_effect_ramp:
        # Cap reactive base/effect brightness to the fading global level for the
        # duration of the ramp, mirroring the generic loop-effect branch below.
        # Without this the per-key base stays at full brightness while only the
        # engine state fades, so the brightness guard staircases the visible
        # restore (+8/frame) and the configured fade duration has no effect.
        lifecycle_lock = getattr(tray.engine, "_start_lock", None)
        if lifecycle_lock is not None:
            with lifecycle_lock:
                _reactive_support.set_engine_attr(
                    tray.engine,
                    "_reactive_follow_global_brightness",
                    True,
                )
                fade_generation = _effect_generation(tray.engine)
        else:
            _reactive_support.set_engine_attr(tray.engine, "_reactive_follow_global_brightness", True)
            fade_generation = _effect_generation(tray.engine)
        fade_completed = False
        try:
            tray.engine.set_brightness(
                target_brightness,
                apply_to_hardware=False,
                fade=True,
                fade_duration_s=float(fade_in_duration_s),
            )
            fade_completed = True
        finally:

            def _finalize_owned_fade() -> None:
                fade_still_owned = fade_generation is not None and _effect_generation(tray.engine) == fade_generation
                if fade_completed and fade_still_owned:
                    _seed_post_fade_reactive_release(
                        tray,
                        from_brightness=int(target_brightness),
                        duration_s=float(fade_in_duration_s),
                    )
                if fade_still_owned:
                    _reactive_support.set_engine_attr(
                        tray.engine,
                        "_reactive_follow_global_brightness",
                        False,
                    )

            if lifecycle_lock is not None:
                with lifecycle_lock:
                    _finalize_owned_fade()
            else:
                _finalize_owned_fade()
        return

    follow_global_flag = False
    saved_reactive_br = None
    saved_perkey_br = None
    if plan.apply_to_hardware:
        saved_reactive_br = getattr(tray.engine, "reactive_brightness", None)
        tray.engine.reactive_brightness = start_brightness
        saved_perkey_br = getattr(tray.engine, "per_key_brightness", None)
        if saved_perkey_br is not None:
            tray.engine.per_key_brightness = start_brightness
    else:
        follow_global_flag = True
        _reactive_support.set_engine_attr(tray.engine, "_reactive_follow_global_brightness", True)

    if plan.apply_to_hardware:
        tray.engine.set_brightness(
            target_brightness,
            apply_to_hardware=True,
            fade=True,
            fade_duration_s=float(fade_in_duration_s),
        )
    else:
        tray.engine.set_brightness(
            target_brightness,
            apply_to_hardware=False,
            fade=True,
            fade_duration_s=float(fade_in_duration_s),
        )

    if follow_global_flag:
        _reactive_support.set_engine_attr(tray.engine, "_reactive_follow_global_brightness", False)

    if saved_reactive_br is not None:
        try:
            tray.engine.reactive_brightness = int(saved_reactive_br)
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
    if saved_perkey_br is not None:
        try:
            tray.engine.per_key_brightness = int(saved_perkey_br)
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
