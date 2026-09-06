"""Commit implementations for the sleep/wake deck pipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from keyrgb.tray._deck_state_store import _completed_lit_state, _store_deck_state
from keyrgb.tray.deck_state import DeckState, SleepWakeIntentKind
from keyrgb.tray.idle_power_state import dim_temp_target_brightness, is_dim_temp_active, set_idle_power_state_field
from keyrgb.tray.pollers.hardware import _controller_sleep, _recovery
from keyrgb.tray.pollers.hardware._decisions import CONFIG_BRIGHTNESS_MAX

if TYPE_CHECKING:
    from keyrgb.tray.protocols import IdlePowerTrayProtocol

logger = logging.getLogger("keyrgb.tray.deck_pipeline")

RecoverFn = Callable[..., bool]
StopEngineFn = Callable[..., bool]
ClearPostStopFn = Callable[..., None]
RestartWakeFn = Callable[..., bool]


def _commit_controller_sleep(
    tray: IdlePowerTrayProtocol,
    *,
    now: float,
    stop_engine: StopEngineFn | None,
    clear_post_stop: ClearPostStopFn | None,
) -> bool:
    _recovery.set_controller_sleep_off(tray, True, now=now)
    tray.is_off = True
    stopper = stop_engine or _controller_sleep.stop_engine_for_controller_sleep_best_effort
    clearer = clear_post_stop or _controller_sleep.clear_post_stop_write_best_effort
    if stopper(tray):
        clearer(tray)
    _recovery._log_polled_hardware_event(tray, "controller_sleep_off")
    _recovery._refresh_ui_without_icon_animation(tray)
    _store_deck_state(tray, DeckState.CONTROLLER_SLEEP_DARK)
    return True


def _commit_firmware_wake(
    tray: IdlePowerTrayProtocol,
    *,
    now: float,
    current_brightness: int,
    dim_temp_target: int | None,
    restart_firmware_wake: RestartWakeFn | None,
) -> bool:
    restarter = restart_firmware_wake or _controller_sleep.restart_effect_after_firmware_wake_best_effort
    _recovery._seed_reactive_restore_damp_best_effort(tray)
    if _controller_sleep._callback_accepts_controller_handoff(restarter):
        restored = restarter(
            tray,
            now=now,
            brightness_override=dim_temp_target,
            controller_brightness_handoff=int(current_brightness),
        )
    else:
        restored = restarter(tray, now=now, brightness_override=dim_temp_target)
    if not restored:
        _recovery._log_polled_hardware_event(
            tray,
            "controller_sleep_firmware_wake",
            effect_restored=False,
        )
        return False
    _recovery.set_controller_sleep_off(tray, False)
    tray.is_off = False
    if _recovery.controller_sleep_resume_guard_active(tray):
        _recovery.set_controller_sleep_resume_guard(tray, False)
    _recovery._log_polled_hardware_event(
        tray,
        "controller_sleep_firmware_wake",
        effect_restored=bool(restored),
    )
    _store_deck_state(tray, _completed_lit_state(tray))
    _recovery._refresh_ui_without_icon_animation(tray)
    return True


_IDLE_INTENT_ACTIONS = {
    SleepWakeIntentKind.IDLE_TURN_OFF: "turn_off",
    SleepWakeIntentKind.DIM_TO_TEMP: "dim_to_temp",
    SleepWakeIntentKind.RESTORE_BRIGHTNESS: "restore_brightness",
    SleepWakeIntentKind.SCREEN_WAKE: "restore",
}


def _commit_keyboard_wake(
    tray: IdlePowerTrayProtocol,
    *,
    now: float,
    dim_temp_target: int | None,
) -> bool:
    effective_dim_target = dim_temp_target
    if effective_dim_target is None and is_dim_temp_active(tray):
        effective_dim_target = dim_temp_target_brightness(tray)
    _recovery._seed_reactive_restore_damp_best_effort(tray)
    restored = _controller_sleep.restart_effect_after_firmware_wake_best_effort(
        tray,
        now=now,
        brightness_override=effective_dim_target,
        controller_brightness_handoff=CONFIG_BRIGHTNESS_MAX,
    )
    if not restored:
        logger.warning("Controller-sleep native wake handoff failed")
        return False
    _recovery.set_controller_sleep_off(tray, False)
    set_idle_power_state_field(
        tray,
        attr_name="_idle_forced_off",
        state_name="idle_forced_off",
        value=False,
    )
    tray.is_off = False
    if _recovery.controller_sleep_resume_guard_active(tray):
        _recovery.set_controller_sleep_resume_guard(tray, False)
    logger.info("EVENT idle_power:controller_sleep_native_wake_handoff trigger=keyboard_evdev")
    _store_deck_state(tray, _completed_lit_state(tray))
    _recovery._refresh_ui_without_icon_animation(tray)
    return True


def _commit_idle_action(
    tray: IdlePowerTrayProtocol,
    kind: SleepWakeIntentKind,
    *,
    dim_temp_brightness: int | None,
) -> bool:
    from keyrgb.core.effects.catalog import REACTIVE_EFFECTS, SW_EFFECTS_SET
    from keyrgb.tray.pollers.idle_power._actions import apply_idle_action, restore_from_idle

    action = _IDLE_INTENT_ACTIONS.get(kind)
    if action is None:
        return False
    reactive_effects_set, sw_effects_set = frozenset(REACTIVE_EFFECTS), SW_EFFECTS_SET
    apply_idle_action(
        tray,
        action=action,
        dim_temp_brightness=int(dim_temp_brightness or 0),
        restore_from_idle_fn=restore_from_idle,
        reactive_effects_set=reactive_effects_set,
        sw_effects_set=sw_effects_set,
    )
    if kind is SleepWakeIntentKind.IDLE_TURN_OFF:
        _store_deck_state(tray, DeckState.IDLE_OFF)
    elif kind is SleepWakeIntentKind.DIM_TO_TEMP:
        _store_deck_state(tray, DeckState.DIM_TEMP)
    else:
        _store_deck_state(tray, _completed_lit_state(tray))
    return True


def _commit_stable_zero_heal(
    tray: IdlePowerTrayProtocol,
    *,
    current_brightness: int,
    recover_stable_zero: RecoverFn | None,
) -> bool:
    stable_recover = recover_stable_zero or _recovery._recover_stable_zero_brightness_best_effort
    if stable_recover(tray, current_brightness=int(current_brightness)):
        _store_deck_state(tray, _completed_lit_state(tray))
        return True
    return False
