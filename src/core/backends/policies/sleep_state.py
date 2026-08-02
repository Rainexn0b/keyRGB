"""Backend-declared controller sleep-state policy."""

from __future__ import annotations

SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF = "zero_brightness_without_off"

_DEFAULT_POLICY = SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF


def normalize_sleep_state_policy(policy: object) -> str:
    value = str(policy or _DEFAULT_POLICY).strip().lower()
    if value == SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF:
        return SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF
    return _DEFAULT_POLICY


def sleep_state_policy(kb: object) -> str:
    return normalize_sleep_state_policy(getattr(kb, "keyrgb_sleep_state_policy", None))


def is_controller_sleep_state(kb: object, *, brightness: int, is_off: bool) -> bool:
    """Whether a polled state means the controller put itself to sleep."""

    try:
        level = int(brightness)
        off = bool(is_off)
    except (TypeError, ValueError, OverflowError):
        return False

    policy = sleep_state_policy(kb)
    if policy == SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF:
        return level == 0 and not off
    return False
