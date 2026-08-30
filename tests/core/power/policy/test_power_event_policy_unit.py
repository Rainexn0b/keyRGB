from __future__ import annotations

from keyrgb.core.power.policies.power_event_policy import (
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


def test_stale_saved_intent_cleared_when_resume_disabled() -> None:
    """KSW-6: a disabled resume must not leave stale intent for a later cycle.

    Sequence: suspend enabled (keyboard on) -> resume while management disabled
    -> user manually turns keyboard off -> re-enable -> second suspend (keyboard
    now off) -> resume enabled. The second resume must NOT restore, because the
    keyboard was genuinely off at the second suspend.
    """

    policy = PowerEventPolicy()

    # Cycle 1: suspend enabled while on, resume while management disabled.
    off1 = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert off1.actions == (TurnOffKeyboard(),)
    res1 = policy.handle_power_restore_event(PowerEventInputs(enabled=False, action_enabled=True, is_off=False))
    assert res1.actions == ()

    # Management re-enabled; user has manually turned the keyboard off.
    # Cycle 2: suspend enabled while now off.
    off2 = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=True))
    assert off2.actions == (TurnOffKeyboard(),)

    # Resume enabled: the keyboard was off at the second suspend, so no restore.
    res2 = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=True))
    assert res2.actions == ()


def test_disabled_off_event_clears_stale_saved_intent() -> None:
    """KSW-6 mirror: a disabled off event must drop any unmatched saved intent.

    If management is toggled off across a suspend boundary, a subsequent enabled
    resume with no matching enabled save must be a no-op rather than replaying
    the stale cycle's intent.
    """

    policy = PowerEventPolicy()

    # Stale save from a previous unmatched cycle.
    policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))

    # A suspend off event arrives while management is disabled.
    disabled_off = policy.handle_power_off_event(PowerEventInputs(enabled=False, action_enabled=True, is_off=False))
    assert disabled_off.actions == ()

    # Re-enable; an enabled resume with no matching enabled save is a no-op.
    restore = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert restore.actions == ()


def test_overlapping_lid_and_suspend_saves_once_restores_once() -> None:
    """Normal lid+suspend overlap still saves intent once and restores once.

    Disabling management mid-cycle must not alter the ordinary overlapping
    behavior while management stays enabled.
    """

    policy = PowerEventPolicy()

    # Lid close (suspend intent) while on.
    lid_close = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert lid_close.actions == (TurnOffKeyboard(),)

    # System suspend while lid already closed: still issues turn-off but intent
    # was already saved once.
    suspend = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert suspend.actions == (TurnOffKeyboard(),)

    # Resume from suspend restores once.
    resume = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert resume.actions == (RestoreKeyboard(),)

    # Lid open after the resume: intent already consumed, no second restore.
    lid_open = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert lid_open.actions == ()


def test_per_action_disabled_still_records_state_when_global_enabled() -> None:
    """Disabling a per-action flag must not clear saved intent (KSW-6 contrast).

    Global management stays enabled; only the specific action is disabled. The
    save/restore pairing must survive exactly as in the existing record test.
    """

    policy = PowerEventPolicy()

    off = policy.handle_power_off_event(PowerEventInputs(enabled=True, action_enabled=False, is_off=False))
    assert off.actions == ()

    restore = policy.handle_power_restore_event(PowerEventInputs(enabled=True, action_enabled=True, is_off=False))
    assert restore.actions == (RestoreKeyboard(),)
