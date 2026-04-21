"""Internal coordination helpers for lighting effect startup and transitions.

This module encapsulates the non-public coordination logic extracted from
lighting_controller.py to reduce file size while preserving the stable
start_current_effect() public facade.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.tray.protocols import LightingTrayProtocol


@dataclass(frozen=True)
class _FadeRampPlan:
    """Plan for how to apply brightness fade ramps to an effect starting."""

    will_fade: bool
    is_loop_effect: bool
    apply_to_hardware: bool


@dataclass(frozen=True)
class _StartCurrentEffectPlan:
    """Classification of the effect being started."""

    effect: str
    is_perkey_mode: bool
    is_none_mode: bool
    is_loop_effect: bool
    restore_secondary_targets: bool


def _coerce_brightness_override(brightness_override: object, *, default: int) -> int:
    """Coerce brightness override to valid range [0, 50]; return default on error."""
    try:
        value = int(brightness_override)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0, min(50, value))


def _plan_effect_fade_ramp(
    *, effect: str, fade_in: bool, start_brightness: int, target_brightness: int, is_software_effect_fn: Callable[[str], bool], is_reactive_effect_fn: Callable[[str], bool]
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

    saved_reactive_br = None
    saved_perkey_br = None
    if plan.apply_to_hardware:
        saved_reactive_br = getattr(tray.engine, "reactive_brightness", None)
        tray.engine.reactive_brightness = start_brightness
        saved_perkey_br = getattr(tray.engine, "per_key_brightness", None)
        if saved_perkey_br is not None:
            tray.engine.per_key_brightness = start_brightness

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
        )

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

