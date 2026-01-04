from __future__ import annotations

from src.core.power_policies.power_event_policy import (
    PowerEventInputs,
    PowerEventPolicy,
    RestoreKeyboard,
    TurnOffKeyboard,
)


def test_event_policy_turns_off_and_restores_when_was_on() -> None:
    policy = PowerEventPolicy()

    off_res = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert off_res.actions == (TurnOffKeyboard(),)

    restore_res = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert restore_res.actions == (RestoreKeyboard(),)


def test_event_policy_does_not_restore_if_already_off() -> None:
    policy = PowerEventPolicy()

    _ = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=True))

    restore_res = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=True))
    assert restore_res.actions == ()


def test_event_policy_ignores_events_when_disabled() -> None:
    policy = PowerEventPolicy()

    res = policy.handle_power_off_event(PowerEventInputs(enabled=False, action_enabled=True, is_off=False))
    assert res.actions == ()

    res2 = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=False, is_off=False))
    assert res2.actions == ()


def test_event_policy_records_state_even_when_off_action_disabled() -> None:
    """If we don't turn off on suspend, we should still restore on resume.

    Some devices reset their lighting across suspend/resume. In that case, the
    user's intent is represented by 'restore_on_resume', even if they have
    disabled 'turn_off_on_suspend'.
    """

    policy = PowerEventPolicy()

    off_res = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=False, is_off=False))
    assert off_res.actions == ()

    restore_res = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert restore_res.actions == (RestoreKeyboard(),)
