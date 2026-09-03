"""Sleep/wake commit pipeline.

Low-frequency brightness/off writes go through ``commit_sleep_wake_intent``.
``next_state`` decides; this module executes. Hardware polling, idle, power,
and menu paths should observe and enqueue intents rather than writing the
device themselves.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

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

    # Preserve the legacy sentinel contract verified by
    # ``power_restore_impl``: when ``user_forced_off`` holds, lower-priority
    # forced-off flags must remain untouched.  Reading all three at once via
    # ``read_forced_off_flags`` would converge sentinels, so short-circuit
    # with individual bridge reads.
    try:
        from keyrgb.tray.idle_power_state import read_idle_power_state_bool_field as _read_bool

        user_forced_off = _read_bool(
            tray, attr_name="_user_forced_off", state_name="user_forced_off", default=False
        )
        if user_forced_off:
            return DeckState.USER_OFF
        power_forced_off = _read_bool(
            tray, attr_name="_power_forced_off", state_name="power_forced_off", default=False
        )
        if power_forced_off:
            return DeckState.POWER_OFF
        idle_forced_off = _read_bool(
            tray, attr_name="_idle_forced_off", state_name="idle_forced_off", default=False
        )
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


def hardware_apply_deferred(tray: IdlePowerTrayProtocol) -> bool:
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

        user_forced_off = _read_bool(
            tray, attr_name="_user_forced_off", state_name="user_forced_off", default=False
        )
        if user_forced_off:
            return False
        power_forced_off = _read_bool(
            tray, attr_name="_power_forced_off", state_name="power_forced_off", default=False
        )
        if power_forced_off:
            return False
        idle_forced_off = _read_bool(
            tray, attr_name="_idle_forced_off", state_name="idle_forced_off", default=False
        )
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
    if intent_kind in (SleepWakeIntentKind.MANUAL_ON, SleepWakeIntentKind.POWER_RESUME) and _is_bare_is_off(
        tray
    ):
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
    dim_temp_brightness: int | None = None,
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
    if kind is SleepWakeIntentKind.KEYBOARD_WAKE:
        return _commit_keyboard_wake(tray)
    if kind in {
        SleepWakeIntentKind.IDLE_TURN_OFF,
        SleepWakeIntentKind.DIM_TO_TEMP,
        SleepWakeIntentKind.RESTORE_BRIGHTNESS,
        SleepWakeIntentKind.SCREEN_WAKE,
    }:
        return _commit_idle_action(tray, kind, dim_temp_brightness=dim_temp_brightness)
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


_IDLE_INTENT_ACTIONS = {
    SleepWakeIntentKind.IDLE_TURN_OFF: "turn_off",
    SleepWakeIntentKind.DIM_TO_TEMP: "dim_to_temp",
    SleepWakeIntentKind.RESTORE_BRIGHTNESS: "restore_brightness",
    SleepWakeIntentKind.SCREEN_WAKE: "restore",
}


def _commit_keyboard_wake(tray: IdlePowerTrayProtocol) -> bool:
    from keyrgb.tray.pollers.idle_power._actions import restore_from_idle

    try:
        tray.engine.turn_off()
    except (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError):
        logger.warning("Controller-sleep hardware re-arm failed", exc_info=True)
        return False
    logger.info("EVENT idle_power:controller_sleep_rearm trigger=keyboard_evdev")
    restore_from_idle(tray)
    _store_deck_state(tray, _completed_lit_state(tray))
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


def commit_lighting_power_intent(
    tray: IdlePowerTrayProtocol,
    intent_kind: SleepWakeIntentKind,
    leaf_fn: Callable[[], object],
    *,
    now: float | None = None,
    respect: bool | None = None,
    guards: SleepWakeGuards | None = None,
    fade_in_duration_s: float | None = None,
) -> bool:
    """Pipeline decision for menu/power ``is_off`` writes.

    The four ``lighting_controller`` entrypoints (``turn_on``, ``turn_off``,
    ``power_turn_off``, ``power_restore``) must be decided by
    ``DeckPipeline`` using ``MANUAL_ON``/``MANUAL_OFF``/``POWER_OFF``/
    ``POWER_RESUME`` before their existing device-writing leaves run.  This
    helper owns that decision plus the ``RESTORING`` firewall:

    * bare ``tray.is_off=True`` with no forced-off flag is treated as
      ``POWER_OFF`` only for ``MANUAL_ON``/``POWER_RESUME`` via the narrow
      override (``hardware_apply_deferred`` stays false);
    * a restoring leaf publishes ``RESTORING`` before it blocks on its fade,
      then ``LIT``/``DIM_TEMP`` on success or the origin on failure;
    * a second wake intent while ``RESTORING`` coalesces via
      ``next_state(RESTORING, wake) -> noop``.
    """

    origin = derive_deck_state(tray)
    now_val = float(now if now is not None else time.monotonic())
    respect_val = respect_enabled(tray) if respect is None else bool(respect)
    guards_val = guards if guards is not None else build_guards(tray, now=now_val)
    plan = decide_sleep_wake(
        tray,
        SleepWakeIntent(intent_kind),
        now=now_val,
        respect=respect_val,
        guards=guards_val,
    )
    if plan.deferred:
        return False
    if not plan.should_commit:
        # Power restore must still run its housekeeping (last_resume_at, guard
        # clear) even when the pipeline correctly blocks the restore while
        # USER_OFF/IDLE_OFF remains authoritative.
        if intent_kind is SleepWakeIntentKind.POWER_RESUME and origin in (
            DeckState.USER_OFF,
            DeckState.IDLE_OFF,
        ):
            leaf_fn()
        return False

    if plan.state is DeckState.RESTORING:
        _store_deck_state(tray, DeckState.RESTORING)
        seeded = _seed_lighting_power_restore_windows(
            tray,
            fade_in_duration_s=fade_in_duration_s,
        )
        leaf_completed = False
        try:
            leaf_result = leaf_fn()
            leaf_completed = True
        finally:
            if seeded:
                _consume_lighting_power_restore_seed(tray)
            if not leaf_completed:
                # Preserve the caller-visible exception while repairing the
                # pipeline state so later intents are not stranded RESTORING.
                _store_deck_state(tray, origin)

        success = leaf_result is not False
        if intent_kind in (SleepWakeIntentKind.MANUAL_ON, SleepWakeIntentKind.POWER_RESUME):
            try:
                if bool(getattr(tray, "is_off", False)):
                    success = False
            except (AttributeError, TypeError, ValueError):
                pass

        if success:
            dim_active = is_dim_temp_active(tray)
            guards2 = SleepWakeGuards(dim_temp_still_active=bool(dim_active))
            plan2 = next_state(
                DeckState.RESTORING,
                SleepWakeIntent(SleepWakeIntentKind.RESTORE_COMPLETE),
                respect=respect_val,
                guards=guards2,
            )
            if plan2.should_commit:
                _store_deck_state(tray, plan2.state)
            else:
                _store_deck_state(tray, _completed_lit_state(tray))
            return True

        guards2 = SleepWakeGuards(dim_temp_still_active=is_dim_temp_active(tray))
        plan2 = next_state(
            DeckState.RESTORING,
            SleepWakeIntent(SleepWakeIntentKind.RESTORE_FAILED, restore_origin=origin),
            respect=respect_val,
            guards=guards2,
        )
        if plan2.should_commit:
            _store_deck_state(tray, plan2.state)
        else:
            _store_deck_state(tray, origin)
        return False

    leaf_fn()
    _store_deck_state(tray, plan.state)
    return True


def _seed_lighting_power_restore_windows(
    tray: IdlePowerTrayProtocol,
    *,
    fade_in_duration_s: float | None,
) -> bool:
    """Enter the shared one-seed contract for manual/power reactive restores."""

    from keyrgb.core.effects.catalog import REACTIVE_EFFECTS
    from keyrgb.core.effects.reactive._reactive_restore_seed import seed_reactive_restore_windows
    from keyrgb.core.utils.safe_attrs import safe_str_attr
    from keyrgb.tray.controllers._power._transition_constants import idle_fade_duration_s

    effect = safe_str_attr(getattr(tray, "config", None), "effect", default="none") or "none"
    if effect not in REACTIVE_EFFECTS:
        return False
    duration = (
        idle_fade_duration_s(tray.config)
        if fade_in_duration_s is None
        else max(0.0, float(fade_in_duration_s))
    )
    try:
        return bool(
            seed_reactive_restore_windows(
                tray.engine,
                fade_in_duration_s=float(duration),
            )
        )
    except (AttributeError, TypeError, ValueError):
        logger.warning("Reactive lighting-power restore seed failed", exc_info=True)
        return False


def _consume_lighting_power_restore_seed(tray: IdlePowerTrayProtocol) -> None:
    """Consume only the original seed when a restart did not consume it."""

    from keyrgb.core.effects.reactive._reactive_restore_seed import apply_queued_reactive_restore_seed

    try:
        apply_queued_reactive_restore_seed(tray.engine)
    except (AttributeError, TypeError, ValueError):
        logger.warning("Reactive lighting-power restore seed cleanup failed", exc_info=True)


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
