from __future__ import annotations

import pytest

from keyrgb.core.backends.policies.wake_settle import (
    DEFAULT_CONTROLLER_WAKE_SETTLE_S,
    controller_wake_settle_s,
    normalize_controller_wake_settle_s,
)


def test_default_is_conservative() -> None:
    assert DEFAULT_CONTROLLER_WAKE_SETTLE_S == 2.5


def test_missing_attribute_fails_closed_to_default() -> None:
    assert controller_wake_settle_s(object()) == 2.5
    assert controller_wake_settle_s(None) == 2.5


def test_explicit_values_preserved_exactly() -> None:
    class _Kb:
        keyrgb_controller_wake_settle_s = 2.5

    assert controller_wake_settle_s(_Kb()) == 2.5
    assert normalize_controller_wake_settle_s(2.5) == 2.5
    assert normalize_controller_wake_settle_s(1) == 1.0
    assert normalize_controller_wake_settle_s(0.146) == pytest.approx(0.146)


@pytest.mark.parametrize(
    "value",
    [None, True, False, -1.0, -0.5, -2, float("nan"), float("inf"), float("-inf"), "2.5", "bad", object()],
)
def test_invalid_values_fail_closed_to_default(value: object) -> None:
    assert normalize_controller_wake_settle_s(value) == 2.5


def test_explicit_zero_disables_settling() -> None:
    assert normalize_controller_wake_settle_s(0) == 0.0
    assert normalize_controller_wake_settle_s(0.0) == 0.0

    class _ZeroKb:
        keyrgb_controller_wake_settle_s = 0.0

    assert controller_wake_settle_s(_ZeroKb()) == 0.0


def test_invalid_device_attribute_fails_closed() -> None:
    class _BadKb:
        keyrgb_controller_wake_settle_s = "2.5"

    class _NegativeKb:
        keyrgb_controller_wake_settle_s = -1.0

    class _BoolKb:
        keyrgb_controller_wake_settle_s = True

    assert controller_wake_settle_s(_BadKb()) == 2.5
    assert controller_wake_settle_s(_NegativeKb()) == 2.5
    assert controller_wake_settle_s(_BoolKb()) == 2.5


def test_ite8291r3_device_declares_wake_settle_override() -> None:
    from keyrgb.core.backends.ite8291r3_perkey.device import Ite8291r3KeyboardDevice

    assert Ite8291r3KeyboardDevice.keyrgb_controller_wake_settle_s == 2.5
    assert controller_wake_settle_s(Ite8291r3KeyboardDevice) == 2.5
