"""Backend-declared controller sleep-state policy.

Some keyboard controllers blank themselves after a firmware inactivity timer
(ite8291r3: ~10 min without physical keypresses) and report that state in a
family-specific way.  The tray hardware poller must recognize "the controller
put itself to sleep" without hardcoding any timeout: the firmware owns the
*when*, KeyRGB only classifies the *what* from the polled state.

Backends declare their signature via the optional ``keyrgb_sleep_state_policy``
device attribute (mirroring ``keyrgb_per_key_mode_policy``).  The default
policy is the ITE8291-family signature, which is also what the pollers matched
before this seam existed — so behavior is unchanged for backends that do not
declare anything.  Additional policies should only be added with hardware
evidence (diagnostics/captures) for the controller in question.
"""

from __future__ import annotations

# The controller reports brightness 0 while still claiming user mode
# (is_off() is False).  Observed on Tongfang ITE8291R3 (0x048d:0x600b family)
# where the firmware sleep blanks the deck but leaves the effect register in
# user mode.
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
    """Whether a polled (brightness, is_off) pair means "controller self-sleep".

    ``kb`` may be None (tests, partial fakes): the default policy applies.
    """

    try:
        level = int(brightness)
        off = bool(is_off)
    except (TypeError, ValueError, OverflowError):
        return False

    policy = sleep_state_policy(kb)
    if policy == SLEEP_STATE_POLICY_ZERO_BRIGHTNESS_WITHOUT_OFF:
        return level == 0 and not off
    return False
