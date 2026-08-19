from __future__ import annotations

from keyrgb.core.backends.policies.sleep_state import (
    SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF,
    is_controller_sleep_state,
    sleep_state_policy,
)


class _Kb:
    keyrgb_sleep_state_policy = "zero_brightness_without_off"


def test_default_policy_matches_ite8291_signature() -> None:
    assert is_controller_sleep_state(None, brightness=0, is_off=False) is True
    assert is_controller_sleep_state(None, brightness=0, is_off=True) is False
    assert is_controller_sleep_state(None, brightness=25, is_off=False) is False


def test_explicit_policy_attribute_is_honored() -> None:
    assert sleep_state_policy(_Kb()) == SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF
    assert is_controller_sleep_state(_Kb(), brightness=0, is_off=False) is True


def test_unknown_policy_falls_back_to_default() -> None:
    class _UnknownKb:
        keyrgb_sleep_state_policy = "some_future_pattern"

    # Unknown policies normalize to the default (pre-seam behavior) until a
    # real signature is added with hardware evidence.
    assert sleep_state_policy(_UnknownKb()) == SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF


def test_unreadable_values_are_not_sleep_state() -> None:
    assert is_controller_sleep_state(None, brightness="bad", is_off=False) is False


def test_ite8291r3_device_declares_default_policy() -> None:
    from keyrgb.core.backends.ite8291r3_perkey.device import Ite8291r3KeyboardDevice

    assert Ite8291r3KeyboardDevice.keyrgb_sleep_state_policy == SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF
