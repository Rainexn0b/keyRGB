"""Sleep/wake commit pipeline.

Low-frequency brightness/off writes go through ``commit_sleep_wake_intent``.
``next_state`` decides; this module executes. Hardware polling, idle, power,
and menu paths should observe and enqueue intents rather than writing the
device themselves.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

logger = logging.getLogger(__name__)

from keyrgb.tray._deck_sleep_wake_commits import (
    _commit_controller_sleep,
    _commit_firmware_wake,
    _commit_idle_action,
    _commit_keyboard_wake,
    _commit_stable_zero_heal,
)
from keyrgb.tray._deck_state_store import _completed_lit_state, _store_deck_state
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
from keyrgb.tray.pollers.hardware import _recovery
from keyrgb.tray.pollers.hardware._decisions import CONFIG_BRIGHTNESS_MAX
from keyrgb.tray.pollers.idle_power._constants import POST_RESUME_IDLE_ACTION_SUPPRESSION_S
from keyrgb.tray.protocols import IdlePowerTrayProtocol

RecoverFn = Callable[..., bool]
StopEngineFn = Callable[..., bool]
ClearPostStopFn = Callable[..., None]
RestartWakeFn = Callable[..., bool]


def derive_deck_state(tray: object) -> DeckState:
    """Map live forced-off / controller-sleep flags onto ``DeckState``.

    SWP-5 will invert this so flags derive from ``DeckState``. Until then the
    flags remain the compatibility seam and the pipeline reads them once per
    decision.
    """

    tray = cast(IdlePowerTrayProtocol, tray)

    owner = ensure_tray_idle_power_state(tray)
    stored = getattr(owner, "deck_state", DeckState.LIT)
    if stored is DeckState.RESTORING:
        return DeckState.RESTORING

    # Preserve the legacy sentinel contract verified by
    # ``power_restore_impl``: when ``user_forced_off`` holds, lower-priority
    # forced-off flags must remain untouched.  Reading all three at once via
    # ``read_forced_off_flags`` would converge sentinels, so short-circuit
    # with individual bridge reads.
    try:
        from keyrgb.tray.idle_power_state import read_idle_power_state_bool_field as _read_bool

        user_forced_off = _read_bool(tray, attr_name="_user_forced_off", state_name="user_forced_off", default=False)
        if user_forced_off:
            return DeckState.USER_OFF
        power_forced_off = _read_bool(tray, attr_name="_power_forced_off", state_name="power_forced_off", default=False)
        if power_forced_off:
            return DeckState.POWER_OFF
        idle_forced_off = _read_bool(tray, attr_name="_idle_forced_off", state_name="idle_forced_off", default=False)
        if idle_forced_off:
            return DeckState.IDLE_OFF
    except (AttributeError, TypeError, ValueError):
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


def hardware_apply_deferred(tray: object) -> bool:
    """True when config/scheduler/power-source must persist intent only."""

    return is_off_family(derive_deck_state(tray))


def _is_bare_is_off(tray: IdlePowerTrayProtocol) -> bool:
    """True when ``is_off`` is set with no pipeline off-family owner.

    This is the user-power bug from the baseline: a bare ``tray.is_off=True``
    with no ``*_forced_off`` or ``controller_sleep_off`` still means the deck
    is dark, but ``derive_deck_state`` reports ``LIT``/``DIM_TEMP``.  Config/
    scheduler deferral must keep using ``derive_deck_state`` (so
    ``hardware_apply_deferred`` stays false), while menu/power restore must
    still light the deck.  The override is therefore narrow and only applied
    for ``MANUAL_ON``/``POWER_RESUME`` decisions at the lighting-power
    boundary.
    """

    try:
        is_off = bool(getattr(tray, "is_off", False))
    except (AttributeError, TypeError, ValueError):
        return False
    if not is_off:
        return False
    # Short-circuit reads to preserve sentinel contract: do not touch
    # lower-priority flags when an authoritative higher flag is set.
    try:
        from keyrgb.tray.idle_power_state import read_idle_power_state_bool_field as _read_bool

        user_forced_off = _read_bool(tray, attr_name="_user_forced_off", state_name="user_forced_off", default=False)
        if user_forced_off:
            return False
        power_forced_off = _read_bool(tray, attr_name="_power_forced_off", state_name="power_forced_off", default=False)
        if power_forced_off:
            return False
        idle_forced_off = _read_bool(tray, attr_name="_idle_forced_off", state_name="idle_forced_off", default=False)
        if idle_forced_off:
            return False
    except (AttributeError, TypeError, ValueError):
        try:
            user_forced_off, power_forced_off, idle_forced_off = read_forced_off_flags(tray)
        except (AttributeError, TypeError, ValueError):
            return False
        if user_forced_off or power_forced_off or idle_forced_off:
            return False
    if _recovery.controller_sleep_off_active(tray):
        return False
    try:
        if ensure_tray_idle_power_state(tray).deck_state is DeckState.RESTORING:
            return False
    except (AttributeError, TypeError):
        pass
    base = derive_deck_state(tray)
    return not is_off_family(base)


def _effective_state_for_intent(
    tray: IdlePowerTrayProtocol,
    intent_kind: SleepWakeIntentKind,
    base: DeckState,
) -> DeckState:
    if intent_kind in (SleepWakeIntentKind.MANUAL_ON, SleepWakeIntentKind.POWER_RESUME) and _is_bare_is_off(tray):
        return DeckState.POWER_OFF
    return base


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
    base = derive_deck_state(tray)
    effective = _effective_state_for_intent(tray, intent.kind, base)
    return next_state(
        effective,
        intent,
        respect=respect_enabled(tray) if respect is None else bool(respect),
        now=now,
        guards=guards if guards is not None else build_guards(tray, now=now),
    )


def commit_sleep_wake_intent(
    tray: IdlePowerTrayProtocol,
    intent: SleepWakeIntent,
    *,
    now: float,
    respect: bool | None = None,
    guards: SleepWakeGuards | None = None,
    current_brightness: int = 0,
    dim_temp_target: int | None = None,
    dim_temp_brightness: int | None = None,
    recover_stable_zero: RecoverFn | None = None,
    recover_power_source: RecoverFn | None = None,
    recover_invalid_brightness: RecoverFn | None = None,
    stop_engine: StopEngineFn | None = None,
    clear_post_stop: ClearPostStopFn | None = None,
    restart_firmware_wake: RestartWakeFn | None = None,
) -> bool:
    """Execute one sleep/wake plan. Returns True when a commit ran."""

    kind = intent.kind
    if kind is SleepWakeIntentKind.AUTO_HEAL:
        if int(current_brightness) > CONFIG_BRIGHTNESS_MAX:
            invalid_recover = recover_invalid_brightness or _recovery._recover_invalid_high_brightness_best_effort
            if invalid_recover(
                tray,
                current_brightness=int(current_brightness),
            ):
                tray.is_off = False
                _store_deck_state(tray, _completed_lit_state(tray))
                _recovery.refresh_invalid_high_brightness_recovery_ui_best_effort(tray)
                return True
            # Invalid-high is not a blank. A latched duplicate or failed
            # handoff must not fall through into zero/power blank recovery.
            return False
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
            current_brightness=current_brightness,
            dim_temp_target=dim_temp_target,
            restart_firmware_wake=restart_firmware_wake,
        )
    if kind is SleepWakeIntentKind.AUTO_HEAL:
        return _commit_stable_zero_heal(
            tray,
            current_brightness=current_brightness,
            recover_stable_zero=recover_stable_zero,
        )
    if kind is SleepWakeIntentKind.KEYBOARD_WAKE:
        return _commit_keyboard_wake(tray, now=now, dim_temp_target=dim_temp_target)
    if kind in {
        SleepWakeIntentKind.IDLE_TURN_OFF,
        SleepWakeIntentKind.DIM_TO_TEMP,
        SleepWakeIntentKind.RESTORE_BRIGHTNESS,
        SleepWakeIntentKind.SCREEN_WAKE,
    }:
        return _commit_idle_action(tray, kind, dim_temp_brightness=dim_temp_brightness)
    return False


def commit_lighting_power_intent(
    tray: object,
    intent_kind: SleepWakeIntentKind,
    leaf_fn: Callable[[], object],
    *,
    now: float | None = None,
    respect: bool | None = None,
    guards: SleepWakeGuards | None = None,
    fade_in_duration_s: float | None = None,
) -> bool:
    from keyrgb.tray._deck_lighting_power import commit_lighting_power_intent as _commit

    return _commit(
        cast(IdlePowerTrayProtocol, tray),
        intent_kind,
        leaf_fn,
        now=now,
        respect=respect,
        guards=guards,
        fade_in_duration_s=fade_in_duration_s,
    )


__all__ = [
    "build_guards",
    "commit_lighting_power_intent",
    "commit_sleep_wake_intent",
    "decide_sleep_wake",
    "derive_deck_state",
    "hardware_apply_deferred",
    "is_off_family",
    "recently_restored_at",
    "respect_enabled",
]
