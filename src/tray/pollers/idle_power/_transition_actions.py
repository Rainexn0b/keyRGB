from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol, cast

from src.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET
from src.core.effects.reactive import _render_brightness_support as _reactive_support
from src.core.utils.safe_attrs import safe_str_attr
from src.tray.protocols import (
    IdlePowerTrayProtocol,
    LightingTrayProtocol,
    set_idle_power_state_field,
)


_LOOP_EFFECTS = frozenset(REACTIVE_EFFECTS) | frozenset(SW_EFFECTS_SET)


class _IdleRestoreStartTray(Protocol):
    def _start_current_effect(self, **kwargs: object) -> None: ...


def _start_current_effect_or_none(tray: object) -> Callable[..., object] | None:
    try:
        start_fn = cast(_IdleRestoreStartTray, tray)._start_current_effect
    except AttributeError:
        return None
    if not callable(start_fn):
        return None
    return cast(Callable[..., object], start_fn)


def _refresh_ui_or_none(tray: object) -> Callable[..., None] | None:
    try:
        refresh_fn = cast(IdlePowerTrayProtocol, tray)._refresh_ui
    except AttributeError:
        return None
    if not callable(refresh_fn):
        return None
    return cast(Callable[..., None], refresh_fn)


def _use_idle_restore_loop_effect_ramp(tray: IdlePowerTrayProtocol, *, fade_in: bool) -> bool:
    if not bool(fade_in):
        return False
    effect = safe_str_attr(getattr(tray, "config", None), "effect", default="none") or "none"
    return effect in _LOOP_EFFECTS


def _should_seed_reactive_restore_windows(tray: object, *, fade_in: bool) -> bool:
    if not bool(fade_in):
        return False
    effect = safe_str_attr(getattr(tray, "config", None), "effect", default="none") or "none"
    return effect in REACTIVE_EFFECTS


def _seed_reactive_restore_windows(engine: object, *, fade_in_duration_s: float) -> None:
    """Queue + apply restore damp so first post-start frames are already protected."""

    if engine is None:
        return
    try:
        _reactive_support.seed_reactive_restore_windows(
            cast(object, engine),
            fade_in_duration_s=float(fade_in_duration_s),
        )
    except (AttributeError, TypeError, ValueError):
        return


def start_current_effect_for_idle_restore(
    tray: IdlePowerTrayProtocol,
    *,
    brightness_override: int | None,
    fade_in: bool,
    fade_in_duration_s: float,
) -> None:
    use_loop_effect_ramp = _use_idle_restore_loop_effect_ramp(tray, fade_in=fade_in)
    seed_reactive_restore_windows = _should_seed_reactive_restore_windows(tray, fade_in=fade_in)
    if use_loop_effect_ramp:
        try:
            set_idle_power_state_field(
                tray,
                attr_name="_idle_restore_loop_effect_ramp",
                state_name="idle_restore_loop_effect_ramp",
                value=True,
            )
        except (AttributeError, TypeError):
            use_loop_effect_ramp = False

    engine = getattr(tray, "engine", None)
    # Seed before start so stop()->ReactiveRenderState() re-applies queued damp
    # before the effect thread's first frames (closes long-idle residual flash).
    if seed_reactive_restore_windows:
        _seed_reactive_restore_windows(engine, fade_in_duration_s=fade_in_duration_s)

    start_fn = _start_current_effect_or_none(tray)
    try:
        if callable(start_fn):
            try:
                start_fn(
                    brightness_override=brightness_override,
                    fade_in=bool(fade_in),
                    fade_in_duration_s=fade_in_duration_s,
                )
            except TypeError:
                start_fn()
            if seed_reactive_restore_windows:
                # Refresh timers after start (stop consumed the pre-start queue).
                _seed_reactive_restore_windows(engine, fade_in_duration_s=fade_in_duration_s)
            return

        from src.tray.controllers.lighting_controller import start_current_effect

        start_current_effect(
            cast(LightingTrayProtocol, tray),
            brightness_override=brightness_override,
            fade_in=bool(fade_in),
            fade_in_duration_s=fade_in_duration_s,
        )
        if seed_reactive_restore_windows:
            _seed_reactive_restore_windows(engine, fade_in_duration_s=fade_in_duration_s)
    finally:
        if use_loop_effect_ramp:
            try:
                set_idle_power_state_field(
                    tray,
                    attr_name="_idle_restore_loop_effect_ramp",
                    state_name="idle_restore_loop_effect_ramp",
                    value=False,
                )
            except (AttributeError, TypeError):
                pass


def apply_dim_temp_brightness(
    tray: IdlePowerTrayProtocol,
    *,
    effect: str,
    dim_temp_brightness: int,
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
    soft_off_fade_duration_s: float,
    set_reactive_transition: Callable[..., None],
    set_brightness_best_effort: Callable[..., None],
) -> None:
    from ._effect_route import EffectRoute, apply_to_hardware_for_non_reactive, classify_effect_route

    route = classify_effect_route(effect, reactive_effects_set, sw_effects_set)
    if route == EffectRoute.REACTIVE:
        with tray.engine.kb_lock:
            _reactive_support.set_engine_attr(
                tray.engine,
                "_reactive_disable_pulse_hw_lift_until",
                float(time.monotonic()) + 2.0,
            )
            _reactive_support.set_engine_attr(tray.engine, "_dim_temp_active", True)
            set_reactive_transition(
                tray.engine,
                target_brightness=int(dim_temp_brightness),
                duration_s=soft_off_fade_duration_s,
            )
            _reactive_support.set_engine_attr(tray.engine, "per_key_brightness", dim_temp_brightness)
            set_brightness_best_effort(
                tray.engine,
                dim_temp_brightness,
                apply_to_hardware=False,
                fade=False,
                fade_duration_s=0.0,
            )
        return

    set_brightness_best_effort(
        tray.engine,
        dim_temp_brightness,
        apply_to_hardware=apply_to_hardware_for_non_reactive(route),
        fade=True,
        fade_duration_s=0.25,
    )


def apply_restore_brightness(
    tray: IdlePowerTrayProtocol,
    *,
    effect: str,
    target: int,
    perkey_target: int,
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
    soft_on_fade_duration_s: float,
    set_reactive_transition: Callable[..., None],
    set_engine_hw_brightness_cap: Callable[..., None],
    set_brightness_best_effort: Callable[..., None],
) -> None:
    from ._effect_route import EffectRoute, apply_to_hardware_for_non_reactive, classify_effect_route

    route = classify_effect_route(effect, reactive_effects_set, sw_effects_set)
    if route == EffectRoute.REACTIVE:
        restore_target_hw = max(int(target), int(perkey_target))
        with tray.engine.kb_lock:
            _seed_reactive_restore_windows(
                tray.engine,
                fade_in_duration_s=soft_on_fade_duration_s,
            )
            set_reactive_transition(
                tray.engine,
                target_brightness=restore_target_hw,
                duration_s=soft_on_fade_duration_s,
            )
            set_engine_hw_brightness_cap(tray.engine, None)
            _reactive_support.set_engine_attr(tray.engine, "per_key_brightness", perkey_target)
            set_brightness_best_effort(
                tray.engine,
                target,
                apply_to_hardware=False,
                fade=False,
                fade_duration_s=0.0,
            )
        return

    set_brightness_best_effort(
        tray.engine,
        target,
        apply_to_hardware=apply_to_hardware_for_non_reactive(route),
        fade=True,
        fade_duration_s=0.25,
    )


def refresh_ui_best_effort(
    tray: IdlePowerTrayProtocol,
    *,
    key: str,
    msg: str,
    call_runtime_boundary: Callable[..., bool],
    warning_level: int,
) -> None:
    refresh_fn = _refresh_ui_or_none(tray)
    if callable(refresh_fn):

        def refresh_without_icon_animation() -> None:
            try:
                refresh_fn(animate_icon=False)
            except TypeError:
                refresh_fn()

        call_runtime_boundary(refresh_without_icon_animation, key=key, level=warning_level, msg=msg)


def read_effect_name(
    config: object,
    *,
    log_key: str,
    log_msg: str,
    log_idle_power_exception: Callable[..., None],
    warning_level: int,
    recoverable_effect_name_exceptions: tuple[type[BaseException], ...],
) -> str:
    try:
        return safe_str_attr(config, "effect", default="none") or "none"
    except recoverable_effect_name_exceptions as exc:
        log_idle_power_exception(key=log_key, level=warning_level, msg=log_msg, exc=exc)
        return "none"
