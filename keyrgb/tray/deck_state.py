"""Pure sleep/wake deck-state decision table.

SWP-0 of the sleep/wake brightness pipeline. Runtime pollers do not call this
yet; the table freezes legal transitions and ``controller_sleep_respect``
policy before any commit path moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeckState(str, Enum):
    """Commit-time lighting authority. Off reasons are not combinable."""

    LIT = "lit"
    DIM_TEMP = "dim_temp"
    USER_OFF = "user_off"
    IDLE_OFF = "idle_off"
    POWER_OFF = "power_off"
    CONTROLLER_SLEEP_DARK = "controller_sleep_dark"
    RESTORING = "restoring"


class SleepWakeIntentKind(str, Enum):
    DIM_TO_TEMP = "dim_to_temp"
    RESTORE_BRIGHTNESS = "restore_brightness"
    IDLE_TURN_OFF = "idle_turn_off"
    CONTROLLER_SLEEP = "controller_sleep"
    AUTO_HEAL = "auto_heal"
    KEYBOARD_WAKE = "keyboard_wake"
    FIRMWARE_WAKE = "firmware_wake"
    SCREEN_WAKE = "screen_wake"
    POWER_OFF = "power_off"
    POWER_RESUME = "power_resume"
    MANUAL_ON = "manual_on"
    MANUAL_OFF = "manual_off"
    DEFER_BRIGHTNESS = "defer_brightness"
    RESTORE_COMPLETE = "restore_complete"
    RESTORE_FAILED = "restore_failed"


class RestoreSource(str, Enum):
    KEYBOARD_EVDEV = "keyboard_evdev"
    FIRMWARE_WAKE = "firmware_wake"
    POWER_RESUME = "power_resume"
    SCREEN_WAKE = "screen_wake"
    MANUAL_ON = "manual_on"
    AUTO_HEAL = "auto_heal"


_OFF_FAMILY = frozenset(
    {
        DeckState.USER_OFF,
        DeckState.IDLE_OFF,
        DeckState.POWER_OFF,
        DeckState.CONTROLLER_SLEEP_DARK,
    }
)
_LIT_FAMILY = frozenset({DeckState.LIT, DeckState.DIM_TEMP})
_WAKE_KINDS = frozenset(
    {
        SleepWakeIntentKind.KEYBOARD_WAKE,
        SleepWakeIntentKind.FIRMWARE_WAKE,
        SleepWakeIntentKind.SCREEN_WAKE,
        SleepWakeIntentKind.POWER_RESUME,
        SleepWakeIntentKind.MANUAL_ON,
        SleepWakeIntentKind.AUTO_HEAL,
    }
)
_INTENT_RESTORE_SOURCE = {
    SleepWakeIntentKind.KEYBOARD_WAKE: RestoreSource.KEYBOARD_EVDEV,
    SleepWakeIntentKind.FIRMWARE_WAKE: RestoreSource.FIRMWARE_WAKE,
    SleepWakeIntentKind.SCREEN_WAKE: RestoreSource.SCREEN_WAKE,
    SleepWakeIntentKind.POWER_RESUME: RestoreSource.POWER_RESUME,
    SleepWakeIntentKind.MANUAL_ON: RestoreSource.MANUAL_ON,
    SleepWakeIntentKind.AUTO_HEAL: RestoreSource.AUTO_HEAL,
}


def is_off_family(state: DeckState) -> bool:
    """True when the deck must stay dark and hardware apply is deferred."""

    return state in _OFF_FAMILY


@dataclass(frozen=True, slots=True)
class SleepWakeIntent:
    kind: SleepWakeIntentKind
    restore_origin: DeckState | None = None


@dataclass(frozen=True, slots=True)
class SleepWakeGuards:
    recently_restored: bool = False
    resume_guard: bool = False
    stable_zero_confirmed: bool = False
    idle_restore_requires_keyboard: bool = False
    keyboard_activity: bool = False
    dim_temp_still_active: bool = False


@dataclass(frozen=True, slots=True)
class SleepWakePlan:
    state: DeckState
    should_commit: bool
    deferred: bool = False
    restore_source: RestoreSource | None = None


def _noop(state: DeckState) -> SleepWakePlan:
    return SleepWakePlan(state=state, should_commit=False)


def _commit(state: DeckState, *, restore_source: RestoreSource | None = None) -> SleepWakePlan:
    return SleepWakePlan(state=state, should_commit=True, restore_source=restore_source)


def _restoring(kind: SleepWakeIntentKind) -> SleepWakePlan:
    return _commit(DeckState.RESTORING, restore_source=_INTENT_RESTORE_SOURCE[kind])


def next_state(
    state: DeckState,
    intent: SleepWakeIntent,
    *,
    respect: bool,
    now: float = 0.0,
    guards: SleepWakeGuards | None = None,
) -> SleepWakePlan:
    """Return the next deck state and whether a restore/off commit is allowed.

    ``now`` is reserved for later suppression-window folding (SWP-2). SWP-0
    decisions use explicit ``guards`` so tests stay clock-free.
    """

    del now
    active = SleepWakeGuards() if guards is None else guards
    kind = intent.kind

    if kind is SleepWakeIntentKind.DEFER_BRIGHTNESS:
        return SleepWakePlan(state=state, should_commit=False, deferred=True)

    if kind is SleepWakeIntentKind.MANUAL_OFF:
        if state is DeckState.USER_OFF:
            return _noop(state)
        return _commit(DeckState.USER_OFF)

    if state is DeckState.USER_OFF:
        if kind is SleepWakeIntentKind.MANUAL_ON:
            return _restoring(kind)
        return _noop(state)

    if kind is SleepWakeIntentKind.POWER_OFF:
        if state is DeckState.POWER_OFF:
            return _noop(state)
        return _commit(DeckState.POWER_OFF)

    if state is DeckState.RESTORING:
        return _plan_while_restoring(intent, active)

    if kind is SleepWakeIntentKind.CONTROLLER_SLEEP:
        return _plan_controller_sleep(state, respect=respect, guards=active)

    if kind is SleepWakeIntentKind.AUTO_HEAL:
        return _plan_auto_heal(state, respect=respect, guards=active)

    if kind in _WAKE_KINDS:
        return _plan_wake(state, kind, guards=active)

    if kind is SleepWakeIntentKind.DIM_TO_TEMP:
        if state is DeckState.LIT:
            return _commit(DeckState.DIM_TEMP)
        return _noop(state)

    if kind is SleepWakeIntentKind.RESTORE_BRIGHTNESS:
        if state is DeckState.DIM_TEMP:
            return _commit(DeckState.LIT)
        return _noop(state)

    if kind is SleepWakeIntentKind.IDLE_TURN_OFF:
        if state in _LIT_FAMILY:
            return _commit(DeckState.IDLE_OFF)
        return _noop(state)

    if kind is SleepWakeIntentKind.RESTORE_COMPLETE:
        return _noop(state)

    if kind is SleepWakeIntentKind.RESTORE_FAILED:
        return _noop(state)

    return _noop(state)


def _plan_while_restoring(intent: SleepWakeIntent, guards: SleepWakeGuards) -> SleepWakePlan:
    kind = intent.kind
    if kind is SleepWakeIntentKind.RESTORE_COMPLETE:
        if guards.dim_temp_still_active:
            return _commit(DeckState.DIM_TEMP)
        return _commit(DeckState.LIT)
    if kind is SleepWakeIntentKind.RESTORE_FAILED:
        origin = intent.restore_origin
        if origin is None:
            return _noop(DeckState.RESTORING)
        return _commit(origin)
    if kind in _WAKE_KINDS:
        return _noop(DeckState.RESTORING)
    if kind is SleepWakeIntentKind.IDLE_TURN_OFF:
        return _noop(DeckState.RESTORING)
    if kind is SleepWakeIntentKind.CONTROLLER_SLEEP:
        return _noop(DeckState.RESTORING)
    if kind is SleepWakeIntentKind.DIM_TO_TEMP:
        return _noop(DeckState.RESTORING)
    if kind is SleepWakeIntentKind.RESTORE_BRIGHTNESS:
        return _noop(DeckState.RESTORING)
    return _noop(DeckState.RESTORING)


def _plan_controller_sleep(state: DeckState, *, respect: bool, guards: SleepWakeGuards) -> SleepWakePlan:
    if state not in _LIT_FAMILY:
        return _noop(state)
    if not respect:
        return _noop(state)
    if not guards.stable_zero_confirmed:
        return _noop(state)
    if guards.recently_restored or guards.resume_guard:
        return _noop(state)
    return _commit(DeckState.CONTROLLER_SLEEP_DARK)


def _plan_auto_heal(state: DeckState, *, respect: bool, guards: SleepWakeGuards) -> SleepWakePlan:
    if state not in _LIT_FAMILY:
        return _noop(state)
    # A post-restore zero is a glitch, not a new native sleep. Heal even when
    # respect is on so a just-lit deck does not go dark for a full poll.
    if guards.recently_restored:
        return _restoring(SleepWakeIntentKind.AUTO_HEAL)
    # Resume-guard means a relight already owns the deck; firmware may still
    # report zero. Recover instead of honoring that zero as a new native sleep.
    if guards.resume_guard:
        return _restoring(SleepWakeIntentKind.AUTO_HEAL)
    if respect:
        return _noop(state)
    if not guards.stable_zero_confirmed:
        return _noop(state)
    return _restoring(SleepWakeIntentKind.AUTO_HEAL)


def _plan_wake(state: DeckState, kind: SleepWakeIntentKind, *, guards: SleepWakeGuards) -> SleepWakePlan:
    if kind is SleepWakeIntentKind.MANUAL_ON:
        if state in _OFF_FAMILY:
            return _restoring(kind)
        return _noop(state)

    if kind is SleepWakeIntentKind.POWER_RESUME:
        if state is DeckState.POWER_OFF or state is DeckState.CONTROLLER_SLEEP_DARK:
            return _restoring(kind)
        return _noop(state)

    if kind is SleepWakeIntentKind.KEYBOARD_WAKE:
        if state is DeckState.CONTROLLER_SLEEP_DARK or state is DeckState.IDLE_OFF:
            return _restoring(kind)
        return _noop(state)

    if kind is SleepWakeIntentKind.FIRMWARE_WAKE:
        if state is DeckState.CONTROLLER_SLEEP_DARK:
            return _restoring(kind)
        return _noop(state)

    if kind is SleepWakeIntentKind.SCREEN_WAKE:
        if state is not DeckState.IDLE_OFF:
            return _noop(state)
        if guards.idle_restore_requires_keyboard and not guards.keyboard_activity:
            return _noop(state)
        return _restoring(kind)

    return _noop(state)
