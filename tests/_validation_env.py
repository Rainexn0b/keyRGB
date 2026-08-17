"""Shared default-suite isolation and hardware-tripwire policy."""

from __future__ import annotations

import os

_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, *, default: str = "") -> str:
    return str(os.environ.get(name, default) or "").strip().lower()


def env_is_true(name: str, *, default: str = "") -> bool:
    return env_flag(name, default=default) in _TRUE_VALUES


def env_is_false(name: str, *, default: str = "") -> bool:
    return env_flag(name, default=default) in _FALSE_VALUES


def hardware_opted_in() -> bool:
    return env_is_true("KEYRGB_ALLOW_HARDWARE") or env_is_true("KEYRGB_HW_TESTS")


def access_tripwire_enabled() -> bool:
    """Refuse real /sys writes and USB device-node opens.

    Default-on when hardware is not opted in. Disable with
    ``KEYRGB_TEST_HARDWARE_TRIPWIRE=0``.
    """

    if hardware_opted_in():
        return False
    return not env_is_false("KEYRGB_TEST_HARDWARE_TRIPWIRE")


def usb_import_tripwire_enabled() -> bool:
    """Block ``usb`` imports. Opt-in; too broad for the default suite."""

    if hardware_opted_in():
        return False
    return env_is_true("KEYRGB_TEST_BLOCK_USB_IMPORTS") or env_is_true("KEYRGB_TEST_HARDWARE_TRIPWIRE")


def led_snapshot_tripwire_enabled() -> bool:
    """Compare /sys LED snapshots after each test. Opt-in; host-environment sensitive."""

    if not access_tripwire_enabled():
        return False
    return env_is_true("KEYRGB_TEST_HARDWARE_LED_SNAPSHOT") or env_is_true("KEYRGB_TEST_HARDWARE_TRIPWIRE")
