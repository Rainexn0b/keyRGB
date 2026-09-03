from __future__ import annotations

import pytest

from keyrgb.tray.deck_state import (
    DeckState,
    RestoreSource,
    SleepWakeGuards,
    SleepWakeIntent,
    SleepWakeIntentKind,
    is_off_family,
    next_state,
)
from keyrgb.tray.idle_power_state import TrayIdlePowerState


def _intent(kind: SleepWakeIntentKind, *, restore_origin: DeckState | None = None) -> SleepWakeIntent:
    return SleepWakeIntent(kind=kind, restore_origin=restore_origin)


def _decide(
    state: DeckState,
    kind: SleepWakeIntentKind,
    *,
    respect: bool = False,
    restore_origin: DeckState | None = None,
    **guard_values: object,
) -> tuple[DeckState, bool, bool, RestoreSource | None]:
    plan = next_state(
        state,
        _intent(kind, restore_origin=restore_origin),
        respect=respect,
        guards=SleepWakeGuards(**guard_values),
    )
    return plan.state, plan.should_commit, plan.deferred, plan.restore_source


def test_tray_idle_power_state_defaults_to_lit_deck() -> None:
    owner = TrayIdlePowerState()
    assert owner.deck_state is DeckState.LIT
    assert owner.deferred_brightness is None
    assert owner.deferred_perkey_profile is None
    assert owner.restoring_target is None


@pytest.mark.parametrize(
    "state,expected",
    [
        (DeckState.LIT, False),
        (DeckState.DIM_TEMP, False),
        (DeckState.RESTORING, False),
        (DeckState.USER_OFF, True),
        (DeckState.IDLE_OFF, True),
        (DeckState.POWER_OFF, True),
        (DeckState.CONTROLLER_SLEEP_DARK, True),
    ],
)
def test_off_family_membership(state: DeckState, expected: bool) -> None:
    assert is_off_family(state) is expected


def test_respect_latches_confirmed_sleep_from_lit() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.CONTROLLER_SLEEP,
        respect=True,
        stable_zero_confirmed=True,
    )
    assert (state, commit, deferred, source) == (DeckState.CONTROLLER_SLEEP_DARK, True, False, None)


def test_respect_off_does_not_latch_controller_sleep() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.CONTROLLER_SLEEP,
        respect=False,
        stable_zero_confirmed=True,
    )
    assert (state, commit, deferred, source) == (DeckState.LIT, False, False, None)


def test_respect_off_auto_heals_confirmed_zero() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.AUTO_HEAL,
        respect=False,
        stable_zero_confirmed=True,
    )
    assert (state, commit, deferred, source) == (
        DeckState.RESTORING,
        True,
        False,
        RestoreSource.AUTO_HEAL,
    )


def test_respect_on_does_not_auto_heal_genuine_sleep() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.AUTO_HEAL,
        respect=True,
        stable_zero_confirmed=True,
    )
    assert (state, commit, deferred, source) == (DeckState.LIT, False, False, None)


def test_recently_restored_blocks_controller_sleep_latch() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.CONTROLLER_SLEEP,
        respect=True,
        stable_zero_confirmed=True,
        recently_restored=True,
    )
    assert (state, commit, deferred, source) == (DeckState.LIT, False, False, None)


def test_resume_guard_auto_heals_instead_of_honoring_sleep() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.AUTO_HEAL,
        respect=True,
        stable_zero_confirmed=True,
        resume_guard=True,
    )
    assert (state, commit, deferred, source) == (
        DeckState.RESTORING,
        True,
        False,
        RestoreSource.AUTO_HEAL,
    )


def test_resume_guard_blocks_controller_sleep_latch() -> None:
    state, commit, deferred, source = _decide(
        DeckState.DIM_TEMP,
        SleepWakeIntentKind.CONTROLLER_SLEEP,
        respect=True,
        stable_zero_confirmed=True,
        resume_guard=True,
    )
    assert (state, commit, deferred, source) == (DeckState.DIM_TEMP, False, False, None)


def test_unconfirmed_zero_does_not_latch_or_heal() -> None:
    latched = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.CONTROLLER_SLEEP,
        respect=True,
        stable_zero_confirmed=False,
    )
    healed = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.AUTO_HEAL,
        respect=False,
        stable_zero_confirmed=False,
    )
    assert latched == (DeckState.LIT, False, False, None)
    assert healed == (DeckState.LIT, False, False, None)


def test_recently_restored_zero_heals_even_when_respect_is_on() -> None:
    state, commit, deferred, source = _decide(
        DeckState.LIT,
        SleepWakeIntentKind.AUTO_HEAL,
        respect=True,
        recently_restored=True,
        stable_zero_confirmed=False,
    )
    assert (state, commit, deferred, source) == (
        DeckState.RESTORING,
        True,
        False,
        RestoreSource.AUTO_HEAL,
    )


def test_user_off_holds_against_power_resume_and_keyboard_wake() -> None:
    resume = _decide(DeckState.USER_OFF, SleepWakeIntentKind.POWER_RESUME, respect=True)
    key = _decide(DeckState.USER_OFF, SleepWakeIntentKind.KEYBOARD_WAKE, respect=True)
    heal = _decide(
        DeckState.USER_OFF,
        SleepWakeIntentKind.AUTO_HEAL,
        respect=False,
        stable_zero_confirmed=True,
        recently_restored=True,
    )
    assert resume[0] is DeckState.USER_OFF and resume[1] is False
    assert key[0] is DeckState.USER_OFF and key[1] is False
    assert heal[0] is DeckState.USER_OFF and heal[1] is False


def test_manual_on_clears_user_off() -> None:
    state, commit, deferred, source = _decide(DeckState.USER_OFF, SleepWakeIntentKind.MANUAL_ON)
    assert (state, commit, deferred, source) == (
        DeckState.RESTORING,
        True,
        False,
        RestoreSource.MANUAL_ON,
    )


def test_power_off_holds_against_keyboard_and_auto_heal() -> None:
    key = _decide(DeckState.POWER_OFF, SleepWakeIntentKind.KEYBOARD_WAKE)
    heal = _decide(
        DeckState.POWER_OFF,
        SleepWakeIntentKind.AUTO_HEAL,
        recently_restored=True,
        stable_zero_confirmed=True,
    )
    assert key == (DeckState.POWER_OFF, False, False, None)
    assert heal == (DeckState.POWER_OFF, False, False, None)


def test_power_resume_from_power_off_restores() -> None:
    state, commit, deferred, source = _decide(DeckState.POWER_OFF, SleepWakeIntentKind.POWER_RESUME)
    assert (state, commit, deferred, source) == (
        DeckState.RESTORING,
        True,
        False,
        RestoreSource.POWER_RESUME,
    )


def test_power_resume_does_not_steal_idle_off() -> None:
    state, commit, deferred, source = _decide(DeckState.IDLE_OFF, SleepWakeIntentKind.POWER_RESUME)
    assert (state, commit, deferred, source) == (DeckState.IDLE_OFF, False, False, None)


def test_already_dark_controller_sleep_suspends_without_restore() -> None:
    state, commit, deferred, source = _decide(
        DeckState.CONTROLLER_SLEEP_DARK,
        SleepWakeIntentKind.POWER_OFF,
    )
    assert (state, commit, deferred, source) == (DeckState.POWER_OFF, True, False, None)


def test_dim_temp_is_not_an_off_state() -> None:
    dim = _decide(DeckState.LIT, SleepWakeIntentKind.DIM_TO_TEMP)
    restore = _decide(DeckState.DIM_TEMP, SleepWakeIntentKind.RESTORE_BRIGHTNESS)
    off = _decide(DeckState.DIM_TEMP, SleepWakeIntentKind.IDLE_TURN_OFF)
    assert dim == (DeckState.DIM_TEMP, True, False, None)
    assert restore == (DeckState.LIT, True, False, None)
    assert off == (DeckState.IDLE_OFF, True, False, None)
    assert is_off_family(DeckState.DIM_TEMP) is False


def test_firmware_wake_then_keyboard_wake_does_not_stack() -> None:
    first = _decide(DeckState.CONTROLLER_SLEEP_DARK, SleepWakeIntentKind.FIRMWARE_WAKE)
    second = _decide(DeckState.RESTORING, SleepWakeIntentKind.KEYBOARD_WAKE)
    assert first == (DeckState.RESTORING, True, False, RestoreSource.FIRMWARE_WAKE)
    assert second == (DeckState.RESTORING, False, False, None)


def test_keyboard_wake_then_firmware_wake_does_not_stack() -> None:
    first = _decide(DeckState.CONTROLLER_SLEEP_DARK, SleepWakeIntentKind.KEYBOARD_WAKE)
    second = _decide(DeckState.RESTORING, SleepWakeIntentKind.FIRMWARE_WAKE)
    assert first == (DeckState.RESTORING, True, False, RestoreSource.KEYBOARD_EVDEV)
    assert second == (DeckState.RESTORING, False, False, None)


@pytest.mark.parametrize(
    "kind",
    [
        SleepWakeIntentKind.KEYBOARD_WAKE,
        SleepWakeIntentKind.FIRMWARE_WAKE,
        SleepWakeIntentKind.SCREEN_WAKE,
        SleepWakeIntentKind.POWER_RESUME,
        SleepWakeIntentKind.MANUAL_ON,
        SleepWakeIntentKind.AUTO_HEAL,
    ],
)
def test_no_second_restore_while_restoring(kind: SleepWakeIntentKind) -> None:
    state, commit, deferred, source = _decide(DeckState.RESTORING, kind, recently_restored=True)
    assert (state, commit, deferred, source) == (DeckState.RESTORING, False, False, None)


def test_manual_off_interrupts_restore() -> None:
    state, commit, deferred, source = _decide(DeckState.RESTORING, SleepWakeIntentKind.MANUAL_OFF)
    assert (state, commit, deferred, source) == (DeckState.USER_OFF, True, False, None)


def test_power_off_interrupts_restore() -> None:
    state, commit, deferred, source = _decide(DeckState.RESTORING, SleepWakeIntentKind.POWER_OFF)
    assert (state, commit, deferred, source) == (DeckState.POWER_OFF, True, False, None)


def test_idle_turn_off_does_not_interrupt_restore() -> None:
    state, commit, deferred, source = _decide(DeckState.RESTORING, SleepWakeIntentKind.IDLE_TURN_OFF)
    assert (state, commit, deferred, source) == (DeckState.RESTORING, False, False, None)


def test_screen_wake_from_idle_off_requires_keyboard_when_gated() -> None:
    blocked = _decide(
        DeckState.IDLE_OFF,
        SleepWakeIntentKind.SCREEN_WAKE,
        respect=True,
        idle_restore_requires_keyboard=True,
        keyboard_activity=False,
    )
    allowed = _decide(
        DeckState.IDLE_OFF,
        SleepWakeIntentKind.SCREEN_WAKE,
        respect=True,
        idle_restore_requires_keyboard=True,
        keyboard_activity=True,
    )
    assert blocked == (DeckState.IDLE_OFF, False, False, None)
    assert allowed == (DeckState.RESTORING, True, False, RestoreSource.SCREEN_WAKE)


def test_keyboard_wake_from_idle_off_always_restores() -> None:
    state, commit, deferred, source = _decide(
        DeckState.IDLE_OFF,
        SleepWakeIntentKind.KEYBOARD_WAKE,
        idle_restore_requires_keyboard=True,
        keyboard_activity=True,
    )
    assert (state, commit, deferred, source) == (
        DeckState.RESTORING,
        True,
        False,
        RestoreSource.KEYBOARD_EVDEV,
    )


def test_screen_wake_does_not_wake_controller_sleep() -> None:
    state, commit, deferred, source = _decide(
        DeckState.CONTROLLER_SLEEP_DARK,
        SleepWakeIntentKind.SCREEN_WAKE,
        keyboard_activity=True,
    )
    assert (state, commit, deferred, source) == (DeckState.CONTROLLER_SLEEP_DARK, False, False, None)


def test_firmware_wake_does_not_wake_idle_off() -> None:
    state, commit, deferred, source = _decide(DeckState.IDLE_OFF, SleepWakeIntentKind.FIRMWARE_WAKE)
    assert (state, commit, deferred, source) == (DeckState.IDLE_OFF, False, False, None)


def test_defer_brightness_never_commits() -> None:
    for state in DeckState:
        plan_state, commit, deferred, source = _decide(state, SleepWakeIntentKind.DEFER_BRIGHTNESS)
        assert plan_state is state
        assert commit is False
        assert deferred is True
        assert source is None


def test_restore_complete_lands_on_lit_or_dim_temp() -> None:
    lit = _decide(DeckState.RESTORING, SleepWakeIntentKind.RESTORE_COMPLETE)
    dim = _decide(
        DeckState.RESTORING,
        SleepWakeIntentKind.RESTORE_COMPLETE,
        dim_temp_still_active=True,
    )
    assert lit == (DeckState.LIT, True, False, None)
    assert dim == (DeckState.DIM_TEMP, True, False, None)


@pytest.mark.parametrize(
    "origin",
    [
        DeckState.USER_OFF,
        DeckState.IDLE_OFF,
        DeckState.POWER_OFF,
        DeckState.CONTROLLER_SLEEP_DARK,
        DeckState.LIT,
        DeckState.DIM_TEMP,
    ],
)
def test_restore_failed_returns_to_origin(origin: DeckState) -> None:
    state, commit, deferred, source = _decide(
        DeckState.RESTORING,
        SleepWakeIntentKind.RESTORE_FAILED,
        restore_origin=origin,
    )
    assert (state, commit, deferred, source) == (origin, True, False, None)


def test_restore_failed_without_origin_stays_restoring() -> None:
    state, commit, deferred, source = _decide(DeckState.RESTORING, SleepWakeIntentKind.RESTORE_FAILED)
    assert (state, commit, deferred, source) == (DeckState.RESTORING, False, False, None)


@pytest.mark.parametrize("state", [DeckState.LIT, DeckState.DIM_TEMP])
def test_manual_on_is_noop_while_already_lit(state: DeckState) -> None:
    plan_state, commit, deferred, source = _decide(state, SleepWakeIntentKind.MANUAL_ON)
    assert (plan_state, commit, deferred, source) == (state, False, False, None)


def test_derive_deck_state_follows_forced_off_priority() -> None:
    from types import SimpleNamespace

    from keyrgb.tray.deck_pipeline import derive_deck_state
    from tests.tray.fakes import attach_idle_power_owner, make_idle_power_owner

    tray = SimpleNamespace()
    attach_idle_power_owner(
        tray,
        make_idle_power_owner(user_forced_off=True, power_forced_off=True, idle_forced_off=True),
    )
    assert derive_deck_state(tray) is DeckState.USER_OFF

    attach_idle_power_owner(tray, make_idle_power_owner(power_forced_off=True, idle_forced_off=True))
    assert derive_deck_state(tray) is DeckState.POWER_OFF

    attach_idle_power_owner(tray, make_idle_power_owner(idle_forced_off=True, dim_temp_active=True))
    assert derive_deck_state(tray) is DeckState.IDLE_OFF

    attach_idle_power_owner(tray, make_idle_power_owner(dim_temp_active=True, dim_temp_target_brightness=5))
    assert derive_deck_state(tray) is DeckState.DIM_TEMP

    sleep_tray = SimpleNamespace()
    attach_idle_power_owner(sleep_tray, make_idle_power_owner(controller_sleep_off=True))
    assert derive_deck_state(sleep_tray) is DeckState.CONTROLLER_SLEEP_DARK
