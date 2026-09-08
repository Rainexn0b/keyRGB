"""Controller wake-settle arming / deadline / restart contract (tray stage 1).

Split from ``test_controller_wake_settle_unit.py`` for the release LOC gate;
covers the settle-window arming contract via the ``controller_wake_settle_s``
policy API (a ``keyrgb_controller_wake_settle_s`` attribute on ``engine.kb``):

* arming performs zero hardware writes, no effect start, and no flag clears;
* duplicate firmware/evdev evidence never extends the deadline;
* firmware-first and evdev-first evidence converge on exactly one post-delay
  restart using the actual post-delay sampled brightness;
* forced-off keeps precedence and drops stale pending state.
"""

from __future__ import annotations

import pytest

from tests.tray.pollers.hardware.lifecycle.wake_settle._support import (
    _apply,
    _SettleTray,
    install_monotonic_clock,
)


@pytest.fixture
def clock(monkeypatch):
    return install_monotonic_clock(monkeypatch)


def test_keyboard_wake_arm_defers_without_writes_or_flag_clears(clock) -> None:
    from keyrgb.tray._deck_sleep_wake_commits import _commit_keyboard_wake

    tray = _SettleTray()

    assert _commit_keyboard_wake(tray, now=100.0, dim_temp_target=None) is True

    assert tray.start_calls == []
    assert tray.kb.writes == []
    assert tray.tray_idle_power_state.controller_sleep_off is True
    assert tray.is_off is True
    assert tray.tray_idle_power_state.controller_wake_settle_until == pytest.approx(102.0)
    assert len(tray.settle_events()) == 1
    assert tray.exceptions == []


def test_duplicate_evidence_never_extends_deadline(clock) -> None:
    from keyrgb.tray._deck_sleep_wake_commits import _commit_keyboard_wake

    tray = _SettleTray()
    clock["now"] = 100.0
    assert _apply(tray, brightness=15) == (15, True)

    clock["now"] = 101.0
    assert _commit_keyboard_wake(tray, now=101.0, dim_temp_target=None) is False
    assert _apply(tray, brightness=18, last_brightness=15) == (18, True)

    owner = tray.tray_idle_power_state
    assert owner.controller_wake_settle_until == pytest.approx(102.0)
    assert tray.start_calls == []
    assert tray.kb.writes == []
    assert len(tray.settle_events()) == 1


def test_firmware_first_converges_on_single_post_delay_restart(clock) -> None:
    tray = _SettleTray()

    clock["now"] = 100.0
    assert _apply(tray, brightness=15) == (15, True)
    clock["now"] = 101.0
    assert _apply(tray, brightness=18, last_brightness=15) == (18, True)
    assert tray.start_calls == []
    assert tray.kb.writes == []

    clock["now"] = 102.0
    assert _apply(tray, brightness=30, last_brightness=18) == (30, False)

    assert len(tray.start_calls) == 1
    assert tray.start_calls[0]["controller_brightness_handoff"] == 30
    assert tray.tray_idle_power_state.controller_sleep_off is False
    assert tray.is_off is False
    assert tray.tray_idle_power_state.controller_wake_settle_until == 0.0
    assert tray.kb.writes == []


def test_evdev_first_converges_on_single_restart_from_zero(clock) -> None:
    from keyrgb.tray._deck_sleep_wake_commits import _commit_keyboard_wake

    tray = _SettleTray()
    assert _commit_keyboard_wake(tray, now=100.0, dim_temp_target=None) is True

    clock["now"] = 101.0
    assert _apply(tray, brightness=0) == (0, True)
    assert tray.start_calls == []

    clock["now"] = 102.0
    assert _apply(tray, brightness=0) == (0, False)

    assert len(tray.start_calls) == 1
    assert tray.start_calls[0]["controller_brightness_handoff"] == 0
    assert tray.tray_idle_power_state.controller_sleep_off is False
    assert tray.is_off is False


def test_failed_due_restart_keeps_pending_for_retry(clock) -> None:
    tray = _SettleTray(start_result=False)

    clock["now"] = 100.0
    assert _apply(tray, brightness=15) == (15, True)

    clock["now"] = 102.0
    assert _apply(tray, brightness=30, last_brightness=15) == (30, True)

    owner = tray.tray_idle_power_state
    assert owner.controller_sleep_off is True
    assert tray.is_off is True
    assert owner.controller_wake_settle_until == pytest.approx(102.0)
    assert len(tray.start_calls) == 1

    # A later poll retries without re-arming (no new deadline, no new event).
    tray.start_result = True
    clock["now"] = 103.0
    assert _apply(tray, brightness=30, last_brightness=30) == (30, False)
    assert len(tray.start_calls) == 2
    assert tray.start_calls[1]["controller_brightness_handoff"] == 30
    assert len(tray.settle_events()) == 1


def test_forced_off_blocks_wake_and_clears_stale_pending(clock) -> None:
    tray = _SettleTray()
    clock["now"] = 100.0
    assert _apply(tray, brightness=15) == (15, True)
    assert tray.tray_idle_power_state.controller_wake_settle_until == pytest.approx(102.0)

    tray.tray_idle_power_state.power_forced_off = True
    tray._power_forced_off = True
    clock["now"] = 101.0
    assert _apply(tray, brightness=20, last_brightness=15) == (20, True)

    assert tray.start_calls == []
    assert tray.kb.writes == []
    assert tray.tray_idle_power_state.controller_wake_settle_until == 0.0
    assert tray.tray_idle_power_state.controller_sleep_off is True


def test_new_controller_sleep_clears_pending() -> None:
    from keyrgb.tray._deck_sleep_wake_commits import _commit_controller_sleep
    from keyrgb.tray.pollers.hardware._controller_sleep import arm_controller_wake_settle

    tray = _SettleTray(controller_sleep_off=False, sleep_at=0.0)
    tray.is_off = False
    assert arm_controller_wake_settle(tray, now=100.0) is True

    assert (
        _commit_controller_sleep(
            tray,
            now=101.0,
            stop_engine=lambda _tray: True,
            clear_post_stop=lambda _tray: None,
        )
        is True
    )

    owner = tray.tray_idle_power_state
    assert owner.controller_wake_settle_until == 0.0
    assert owner.controller_sleep_off is True
    assert tray.is_off is True
