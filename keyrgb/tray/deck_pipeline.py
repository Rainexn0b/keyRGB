"""Sleep/wake commit pipeline.

Low-frequency brightness/off writes go through ``commit_sleep_wake_intent``.
``next_state`` decides; this module executes. Hardware polling, idle, power,
and menu paths should observe and enqueue intents rather than writing the
device themselves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from keyrgb.tray.deck_state import (
    DeckState,
    SleepWakeGuards,
    SleepWakeIntent,
    SleepWakeIntentKind,
    SleepWakePlan,
    is_off_family,
    next_state,
)
from keyrgb.tray.idle_power_state import (
    ensure_tray_idle_power_state,
    is_dim_temp_active,
    read_forced_off_flags,
    read_last_resume_at,
)
from keyrgb.tray.pollers.hardware import _controller_sleep, _recovery
from keyrgb.tray.pollers.idle_power._constants import POST_RESUME_IDLE_ACTION_SUPPRESSION_S

if TYPE_CHECKING:
    from keyrgb.tray.protocols import IdlePowerTrayProtocol

RecoverFn = Callable[..., bool]
StopEngineFn = Callable[..., bool]
ClearPostStopFn = Callable[..., None]
RestartWakeFn = Callable[..., bool]


def derive_deck_state(tray: IdlePowerTrayProtocol) -> DeckState:
    """Map live forced-off / controller-sleep flags onto ``DeckState``.

    SWP-5 will invert this so flags derive from ``DeckState``. Until then the
    flags remain the compatibility seam and the pipeline reads them once per
    decision.
    """

    owner = ensure_tray_idle_power_state(tray)
    stored = getattr(owner, "deck_state", DeckState.LIT)
    if stored is DeckState.RESTORING:
        return DeckState.RESTORING

    user_forced_off, power_forced_off, idle_forced_off = read_forced_off_flags(tray)
    if user_forced_off:
        return DeckState.USER_OFF
    if power_forced_off:
        return DeckState.POWER_OFF
    if idle_forced_off:
        return DeckState.IDLE_OFF
    if _recovery.controller_sleep_off_active(tray):
        return DeckState.CONTROLLER_SLEEP_DARK
    if is_dim_temp_active(tray):
        return DeckState.DIM_TEMP
    return DeckState.LIT


def respect_enabled(tray: IdlePowerTrayProtocol) -> bool:
    """Snapshot ``controller_sleep_respect`` once per decision."""

    return bool(_recovery.controller_sleep_respect_enabled(tray))


def recently_restored_at(tray: IdlePowerTrayProtocol, *, now: float) -> bool:
    last_resume_at = float(read_last_resume_at(tray) or 0.0)
    return last_resume_at > 0.0 and (now - last_resume_at) < POST_RESUME_IDLE_ACTION_SUPPRESSION_S


def build_guards(
    tray: IdlePowerTrayProtocol,
    *,
    now: float,
    stable_zero_confirmed: bool = False,
    idle_restore_requires_keyboard: bool = False,
    keyboard_activity: bool = False,
) -> SleepWakeGuards:
    return SleepWakeGuards(
        recently_restored=recently_restored_at(tray, now=now),
        resume_guard=_recovery.controller_sleep_resume_guard_active(tray),
        stable_zero_confirmed=bool(stable_zero_confirmed),
        idle_restore_requires_keyboard=bool(idle_restore_requires_keyboard),
        keyboard_activity=bool(keyboard_activity),
        dim_temp_still_active=is_dim_temp_active(tray),
    )


def decide_sleep_wake(
    tray: IdlePowerTrayProtocol,
    intent: SleepWakeIntent,
    *,
    now: float,
    respect: bool | None = None,
    guards: SleepWakeGuards | None = None,
) -> SleepWakePlan:
    return next_state(
        derive_deck_state(tray),
        intent,
        respect=respect_enabled(tray) if respect is None else bool(respect),
        now=now,
        guards=guards if guards is not None else build_guards(tray, now=now),
    )


def _store_deck_state(tray: IdlePowerTrayProtocol, state: DeckState) -> None:
    try:
        ensure_tray_idle_power_state(tray).deck_state = state
    except (AttributeError, TypeError):
        return


def _completed_lit_state(tray: IdlePowerTrayProtocol) -> DeckState:
    return DeckState.DIM_TEMP if is_dim_temp_active(tray) else DeckState.LIT


def commit_sleep_wake_intent(
    tray: IdlePowerTrayProtocol,
    intent: SleepWakeIntent,
    *,
    now: float,
    respect: bool | None = None,
    guards: SleepWakeGuards | None = None,
    current_brightness: int = 0,
    dim_temp_target: int | None = None,
    recover_stable_zero: RecoverFn | None = None,
    recover_power_source: RecoverFn | None = None,
    stop_engine: StopEngineFn | None = None,
    clear_post_stop: ClearPostStopFn | None = None,
    restart_firmware_wake: RestartWakeFn | None = None,
) -> bool:
    """Execute one sleep/wake plan. Returns True when a commit ran."""

    kind = intent.kind
    if kind is SleepWakeIntentKind.AUTO_HEAL:
        power_recover = recover_power_source or _recovery._recover_recent_power_source_blank_best_effort
        if power_recover(tray, current_brightness=int(current_brightness)):
            _store_deck_state(tray, _completed_lit_state(tray))
            return True

    plan = decide_sleep_wake(tray, intent, now=now, respect=respect, guards=guards)
    if plan.deferred:
        return False
    if not plan.should_commit:
        return False

    if kind is SleepWakeIntentKind.CONTROLLER_SLEEP:
        return _commit_controller_sleep(
            tray,
            now=now,
            stop_engine=stop_engine,
            clear_post_stop=clear_post_stop,
        )
    if kind is SleepWakeIntentKind.FIRMWARE_WAKE:
        return _commit_firmware_wake(
            tray,
            now=now,
            dim_temp_target=dim_temp_target,
            restart_firmware_wake=restart_firmware_wake,
        )
    if kind is SleepWakeIntentKind.AUTO_HEAL:
        return _commit_stable_zero_heal(
            tray,
            current_brightness=current_brightness,
            recover_stable_zero=recover_stable_zero,
        )
    return False


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
    dim_temp_target: int | None,
    restart_firmware_wake: RestartWakeFn | None,
) -> bool:
    _recovery.set_controller_sleep_off(tray, False)
    tray.is_off = False
    if _recovery.controller_sleep_resume_guard_active(tray):
        _recovery.set_controller_sleep_resume_guard(tray, False)
    restarter = restart_firmware_wake or _controller_sleep.restart_effect_after_firmware_wake_best_effort
    restored = restarter(tray, now=now, brightness_override=dim_temp_target)
    _recovery._log_polled_hardware_event(
        tray,
        "controller_sleep_firmware_wake",
        effect_restored=bool(restored),
    )
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


__all__ = [
    "build_guards",
    "commit_sleep_wake_intent",
    "decide_sleep_wake",
    "derive_deck_state",
    "is_off_family",
    "recently_restored_at",
    "respect_enabled",
]
