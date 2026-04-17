from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional

from src.core.utils.safe_attrs import safe_int_attr
from src.tray.controllers._power._transition_constants import SOFT_OFF_FADE_DURATION_S, SOFT_ON_FADE_DURATION_S
from src.tray.pollers.idle_power._transition_actions import (
    apply_dim_temp_brightness,
    apply_restore_brightness,
    read_effect_name,
    refresh_ui_best_effort,
)
from src.tray.protocols import IdlePowerTrayProtocol


def execute_idle_action(
    tray: IdlePowerTrayProtocol,
    *,
    action: Optional[str],
    dim_temp_brightness: int,
    restore_from_idle_fn: Callable[[IdlePowerTrayProtocol], None],
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
    call_runtime_boundary: Callable[..., bool],
    dim_temp_state_matches: Callable[..., bool],
    log_idle_power_exception: Callable[..., None],
    set_engine_hw_brightness_cap: Callable[..., None],
    set_reactive_transition: Callable[..., None],
    set_brightness_best_effort: Callable[..., None],
    recoverable_effect_name_exceptions: tuple[type[BaseException], ...],
) -> None:
    if action == "turn_off":
        _execute_turn_off(
            tray,
            call_runtime_boundary=call_runtime_boundary,
            set_engine_hw_brightness_cap=set_engine_hw_brightness_cap,
        )
        return

    if action == "dim_to_temp":
        _execute_dim_to_temp(
            tray,
            dim_temp_brightness=dim_temp_brightness,
            reactive_effects_set=reactive_effects_set,
            sw_effects_set=sw_effects_set,
            call_runtime_boundary=call_runtime_boundary,
            dim_temp_state_matches=dim_temp_state_matches,
            log_idle_power_exception=log_idle_power_exception,
            set_reactive_transition=set_reactive_transition,
            set_brightness_best_effort=set_brightness_best_effort,
            recoverable_effect_name_exceptions=recoverable_effect_name_exceptions,
        )
        return

    if action == "restore_brightness":
        _execute_restore_brightness(
            tray,
            reactive_effects_set=reactive_effects_set,
            sw_effects_set=sw_effects_set,
            call_runtime_boundary=call_runtime_boundary,
            log_idle_power_exception=log_idle_power_exception,
            set_reactive_transition=set_reactive_transition,
            set_engine_hw_brightness_cap=set_engine_hw_brightness_cap,
            set_brightness_best_effort=set_brightness_best_effort,
            recoverable_effect_name_exceptions=recoverable_effect_name_exceptions,
        )
        return

    if action == "restore":
        _execute_restore(
            tray,
            restore_from_idle_fn=restore_from_idle_fn,
            set_engine_hw_brightness_cap=set_engine_hw_brightness_cap,
        )


def _execute_turn_off(
    tray: IdlePowerTrayProtocol,
    *,
    call_runtime_boundary: Callable[..., bool],
    set_engine_hw_brightness_cap: Callable[..., None],
) -> None:
    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    set_engine_hw_brightness_cap(tray.engine, None)
    call_runtime_boundary(
        lambda: tray.engine.stop(),
        key="idle_power.turn_off.stop_engine",
        level=logging.WARNING,
        msg="Idle-power turn-off failed while stopping engine",
    )
    call_runtime_boundary(
        lambda: tray.engine.turn_off(fade=True, fade_duration_s=SOFT_OFF_FADE_DURATION_S),
        key="idle_power.turn_off.turn_off",
        level=logging.WARNING,
        msg="Idle-power turn-off failed while writing off state",
    )

    tray.is_off = True
    tray._idle_forced_off = True
    refresh_ui_best_effort(
        tray,
        key="idle_power.turn_off.refresh_ui",
        msg="Idle-power UI refresh failed after turn-off",
        call_runtime_boundary=call_runtime_boundary,
        warning_level=logging.WARNING,
    )


def _execute_dim_to_temp(
    tray: IdlePowerTrayProtocol,
    *,
    dim_temp_brightness: int,
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
    call_runtime_boundary: Callable[..., bool],
    dim_temp_state_matches: Callable[..., bool],
    log_idle_power_exception: Callable[..., None],
    set_reactive_transition: Callable[..., None],
    set_brightness_best_effort: Callable[..., None],
    recoverable_effect_name_exceptions: tuple[type[BaseException], ...],
) -> None:
    if bool(tray.is_off):
        return

    if dim_temp_state_matches(tray, target_brightness=dim_temp_brightness):
        return

    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = int(dim_temp_brightness)
    effect = read_effect_name(
        tray.config,
        log_key="idle_power.dim_to_temp.effect_name",
        log_msg="Idle-power dim-to-temp could not read effect name; falling back to none",
        log_idle_power_exception=log_idle_power_exception,
        warning_level=logging.WARNING,
        recoverable_effect_name_exceptions=recoverable_effect_name_exceptions,
    )
    call_runtime_boundary(
        lambda: apply_dim_temp_brightness(
            tray,
            effect=effect,
            dim_temp_brightness=dim_temp_brightness,
            reactive_effects_set=reactive_effects_set,
            sw_effects_set=sw_effects_set,
            soft_off_fade_duration_s=SOFT_OFF_FADE_DURATION_S,
            set_reactive_transition=set_reactive_transition,
            set_brightness_best_effort=set_brightness_best_effort,
        ),
        key="idle_power.dim_to_temp.apply",
        level=logging.WARNING,
        msg="Idle-power dim-to-temp apply failed",
    )


def _execute_restore_brightness(
    tray: IdlePowerTrayProtocol,
    *,
    reactive_effects_set: frozenset[str],
    sw_effects_set: frozenset[str],
    call_runtime_boundary: Callable[..., bool],
    log_idle_power_exception: Callable[..., None],
    set_reactive_transition: Callable[..., None],
    set_engine_hw_brightness_cap: Callable[..., None],
    set_brightness_best_effort: Callable[..., None],
    recoverable_effect_name_exceptions: tuple[type[BaseException], ...],
) -> None:
    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    config = tray.config
    target = safe_int_attr(config, "brightness", default=0)
    perkey_target = safe_int_attr(config, "perkey_brightness", default=0)
    effect = read_effect_name(
        config,
        log_key="idle_power.restore_brightness.read_state",
        log_msg="Idle-power restore could not read brightness state; using safe defaults",
        log_idle_power_exception=log_idle_power_exception,
        warning_level=logging.WARNING,
        recoverable_effect_name_exceptions=recoverable_effect_name_exceptions,
    )
    if target > 0 and not bool(tray.is_off):
        call_runtime_boundary(
            lambda: apply_restore_brightness(
                tray,
                effect=effect,
                target=target,
                perkey_target=perkey_target,
                reactive_effects_set=reactive_effects_set,
                sw_effects_set=sw_effects_set,
                soft_on_fade_duration_s=SOFT_ON_FADE_DURATION_S,
                set_reactive_transition=set_reactive_transition,
                set_engine_hw_brightness_cap=set_engine_hw_brightness_cap,
                set_brightness_best_effort=set_brightness_best_effort,
            ),
            key="idle_power.restore_brightness.apply",
            level=logging.WARNING,
            msg="Idle-power restore-brightness apply failed",
        )


def _execute_restore(
    tray: IdlePowerTrayProtocol,
    *,
    restore_from_idle_fn: Callable[[IdlePowerTrayProtocol], None],
    set_engine_hw_brightness_cap: Callable[..., None],
) -> None:
    if bool(tray._user_forced_off) or bool(tray._power_forced_off):
        return

    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    if hasattr(tray, "engine"):
        set_engine_hw_brightness_cap(tray.engine, None)
    restore_from_idle_fn(tray)
