"""Controller wake-settle policy helpers / edge cases (tray stage 1).

Split from ``test_controller_wake_settle_unit.py`` for the release LOC gate;
covers delay-0 immediate behavior, stale off snapshots, deadline dim policy,
the settle helper API (arm-once/clear/due/remaining), conservative defaults
for undeclared backends, and arm-failure propagation.
"""

from __future__ import annotations

import pytest

from tests.tray.pollers.hardware.lifecycle.wake_settle._support import (
    SETTLE_S,
    _apply,
    _SettleTray,
    install_monotonic_clock,
)


@pytest.fixture
def clock(monkeypatch):
    return install_monotonic_clock(monkeypatch)


def test_delay_zero_preserves_immediate_firmware_wake(clock) -> None:
    tray = _SettleTray(settle_s=0.0)

    clock["now"] = 101.0
    assert _apply(tray, brightness=25) == (25, False)

    assert len(tray.start_calls) == 1
    assert tray.start_calls[0] == {"controller_brightness_handoff": 25}
    assert tray.tray_idle_power_state.controller_sleep_off is False
    assert tray.is_off is False
    assert tray.tray_idle_power_state.controller_wake_settle_until == 0.0


def test_delay_zero_preserves_immediate_keyboard_wake() -> None:
    from keyrgb.tray._deck_sleep_wake_commits import _commit_keyboard_wake
    from keyrgb.tray.pollers.hardware._decisions import CONFIG_BRIGHTNESS_MAX

    tray = _SettleTray(settle_s=0.0)

    assert _commit_keyboard_wake(tray, now=100.0, dim_temp_target=None) is True

    assert len(tray.start_calls) == 1
    assert tray.start_calls[0]["controller_brightness_handoff"] == CONFIG_BRIGHTNESS_MAX
    assert tray.tray_idle_power_state.controller_sleep_off is False
    assert tray.is_off is False


def test_due_off_snapshot_clears_stale_settle_and_later_rearms(clock) -> None:
    from keyrgb.tray.pollers.hardware._controller_sleep import controller_wake_settle_pending

    tray = _SettleTray()
    clock["now"] = 100.0
    assert _apply(tray, brightness=15) == (15, True)
    assert tray.tray_idle_power_state.controller_wake_settle_until == pytest.approx(102.0)

    # Due but still reporting off: the wake evidence went stale. Stay dark
    # with no restart and no surviving deadline.
    clock["now"] = 102.0
    assert _apply(tray, brightness=0, off=True, last_brightness=15) == (0, True)
    assert tray.start_calls == []
    assert tray.kb.writes == []
    assert controller_wake_settle_pending(tray) is False
    assert tray.tray_idle_power_state.controller_sleep_off is True

    # A later nonzero wake arms a fresh full delay from its own evidence.
    clock["now"] = 103.0
    assert _apply(tray, brightness=20, off=False, last_brightness=0) == (20, True)
    assert tray.start_calls == []
    assert tray.tray_idle_power_state.controller_wake_settle_until == pytest.approx(105.0)


def test_firmware_wake_completion_uses_deadline_dim_policy(clock) -> None:
    tray = _SettleTray()
    clock["now"] = 100.0
    assert _apply(tray, brightness=15) == (15, True)

    # Screen dim takes over before the deadline: completion must sample the
    # currently active dim target, with actual brightness as the handoff.
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5
    clock["now"] = 102.0
    assert _apply(tray, brightness=30, last_brightness=15) == (30, False)

    assert len(tray.start_calls) == 1
    assert tray.start_calls[0] == {"brightness_override": 5, "controller_brightness_handoff": 30}

    # Reverse: stale arm-time dim state must not override current policy once
    # the screen has woken again before the deadline.
    tray2 = _SettleTray()
    tray2._dim_temp_active = True
    tray2._dim_temp_target_brightness = 5
    clock["now"] = 100.0
    assert _apply(tray2, brightness=15) == (15, True)
    tray2._dim_temp_active = False
    tray2._dim_temp_target_brightness = None
    clock["now"] = 102.0
    assert _apply(tray2, brightness=30, last_brightness=15) == (30, False)

    assert len(tray2.start_calls) == 1
    assert tray2.start_calls[0] == {"controller_brightness_handoff": 30}


def test_helpers_arm_once_clear_and_zero_delay() -> None:
    from keyrgb.tray.pollers.hardware import _controller_sleep as cs

    tray = _SettleTray(controller_sleep_off=False, sleep_at=0.0)
    tray.is_off = False

    assert cs.controller_wake_settle_delay_s(tray) == pytest.approx(SETTLE_S)
    assert cs.controller_wake_settle_pending(tray) is False
    assert cs.arm_controller_wake_settle(tray, now=100.0) is True
    assert cs.controller_wake_settle_pending(tray) is True
    assert cs.controller_wake_settle_remaining_s(tray, now=99.0) == pytest.approx(3.0)
    assert cs.controller_wake_settle_due(tray, now=101.0) is False
    assert cs.controller_wake_settle_due(tray, now=102.0) is True
    assert cs.arm_controller_wake_settle(tray, now=101.0) is False

    cs.clear_controller_wake_settle(tray)
    assert cs.controller_wake_settle_pending(tray) is False
    assert cs.controller_wake_settle_remaining_s(tray, now=101.0) == 0.0
    assert cs.controller_wake_settle_due(tray, now=103.0) is False

    unconfigured = _SettleTray(settle_s=0.0, controller_sleep_off=False, sleep_at=0.0)
    unconfigured.is_off = False
    assert cs.controller_wake_settle_delay_s(unconfigured) == 0.0
    assert cs.arm_controller_wake_settle(unconfigured, now=100.0) is False
    assert cs.controller_wake_settle_pending(unconfigured) is False


def test_missing_settle_defaults_conservative() -> None:
    from keyrgb.tray.pollers.hardware import _controller_sleep as cs

    tray = _SettleTray(settle_s=None, controller_sleep_off=False, sleep_at=0.0)
    tray.is_off = False
    assert cs.controller_wake_settle_delay_s(tray) == pytest.approx(2.5)
    assert cs.arm_controller_wake_settle(tray, now=100.0) is True
    assert cs.controller_wake_settle_pending(tray) is True


def test_firmware_wake_arm_failure_returns_false(monkeypatch) -> None:
    from keyrgb.tray._deck_sleep_wake_commits import _commit_firmware_wake
    from keyrgb.tray.pollers.hardware import _controller_sleep as cs

    tray = _SettleTray()
    monkeypatch.setattr(cs, "arm_controller_wake_settle", lambda *args, **kwargs: False)

    assert (
        _commit_firmware_wake(
            tray,
            now=100.0,
            current_brightness=15,
            dim_temp_target=None,
            restart_firmware_wake=None,
        )
        is False
    )
    assert tray.start_calls == []
    assert tray.kb.writes == []
    assert tray.tray_idle_power_state.controller_sleep_off is True
