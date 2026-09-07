from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from keyrgb.tray.pollers.hardware_polling import _apply_polled_hardware_state


@dataclass
class _DummyConfig:
    brightness: int


class _DummyTray:
    def __init__(self, *, brightness: int, is_off: bool, power_forced_off: bool = False):
        from tests.tray.fakes import attach_idle_power_owner, make_idle_power_owner

        self.config = _DummyConfig(brightness=brightness)
        self.is_off = is_off
        self.refresh_count = 0
        self.last_animate_icon = None
        attach_idle_power_owner(
            self,
            make_idle_power_owner(
                power_forced_off=power_forced_off,
                last_brightness=brightness if brightness > 0 else 25,
            ),
        )

    def _refresh_ui(self, *, animate_icon: bool = True) -> None:
        self.refresh_count += 1
        self.last_animate_icon = bool(animate_icon)


def test_hardware_polling_recovers_recent_power_source_blank_without_marking_off(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_power_source_transition_at = 100.0
    tray._apply_power_source_perkey_profile_transition = MagicMock(return_value=True)

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    assert last_brightness == 0
    assert last_off is False
    assert tray.is_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False
    assert tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
    assert tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None
    assert tray.tray_idle_power_state.last_power_source_blank_recovery_at == 101.0


def test_hardware_polling_recovers_stable_zero_without_off_state(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._start_current_effect = MagicMock()

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    tray._start_current_effect.assert_called_once_with()
    assert last_brightness == 0
    assert last_off is False
    assert tray.is_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False
    assert tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
    assert tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None
    assert tray.tray_idle_power_state.last_hardware_blank_recovery_at == 200.0


def test_hardware_polling_does_not_recover_stable_zero_when_forced_off(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=True, power_forced_off=True)
    tray._start_current_effect = MagicMock()

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    tray._start_current_effect.assert_not_called()
    assert last_brightness == 0
    assert last_off is True
    assert tray.is_off is True
    assert tray.refresh_count == 0


def test_hardware_polling_stable_zero_recovery_obeys_cooldown(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_hardware_blank_recovery_at = 198.0
    tray._start_current_effect = MagicMock()

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

    _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=False,
    )

    tray._start_current_effect.assert_not_called()
    assert tray.refresh_count == 0
    assert tray.tray_idle_power_state.last_hardware_blank_recovery_at == 198.0


def test_hardware_polling_keeps_recent_power_source_blank_in_recovery_window(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_power_source_transition_at = 100.0

    monkeypatch.setattr("keyrgb.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=True,
        last_brightness=0,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is False
    assert tray.is_off is False
    assert tray.refresh_count == 0


def test_stable_zero_recovers_on_first_zero_read_during_restore_window(monkeypatch) -> None:
    """A transient zero during the post-restore window must not wait for a
    confirmation poll — the keyboard just faded on, so a zero is a glitch."""

    import time

    from keyrgb.tray.idle_power_state import set_idle_power_state_field

    tray = _DummyTray(brightness=25, is_off=False)
    set_idle_power_state_field(
        tray,
        attr_name="_last_resume_at",
        state_name="last_resume_at",
        value=time.monotonic() - 2.0,  # 2s ago, within the suppression window
    )

    recovery_calls: list[int] = []

    def _fake_recover(_tray, *, current_brightness: int) -> bool:
        recovery_calls.append(int(current_brightness))
        return True

    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        _fake_recover,
    )

    # First zero read after restore: last_brightness > 0 (was at 34 mid-fade).
    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=34,
        last_off_state=False,
    )

    assert recovery_calls == [0]
    assert (last_brightness, last_off) == (0, False)


def test_stable_zero_recovers_when_first_post_restore_poll_only_clears_off_state(monkeypatch) -> None:
    """A restored controller can remain at tracked brightness zero while its
    off flag clears. Do not return from off-state bookkeeping and wait another
    full poll before healing that post-restore relapse."""

    import time

    from keyrgb.tray.idle_power_state import set_idle_power_state_field

    tray = _DummyTray(brightness=25, is_off=False)
    set_idle_power_state_field(
        tray,
        attr_name="_last_resume_at",
        state_name="last_resume_at",
        value=time.monotonic() - 2.0,
    )

    recovery_calls: list[int] = []

    def _fake_recover(_tray, *, current_brightness: int) -> bool:
        recovery_calls.append(int(current_brightness))
        return True

    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        _fake_recover,
    )

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert recovery_calls == [0]
    assert (last_brightness, last_off) == (0, False)


def test_off_state_clear_zero_outside_restore_window_waits_for_stable_confirmation(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=True)
    recovery_calls: list[int] = []

    def _fake_recover(_tray, *, current_brightness: int) -> bool:
        recovery_calls.append(int(current_brightness))
        return True

    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        _fake_recover,
    )

    result = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert recovery_calls == []
    assert result == (0, False)


def test_off_state_clear_zero_does_not_recover_without_brightness_intent(monkeypatch) -> None:
    import time

    from keyrgb.tray.idle_power_state import set_idle_power_state_field

    tray = _DummyTray(brightness=0, is_off=True)
    set_idle_power_state_field(
        tray,
        attr_name="_last_resume_at",
        state_name="last_resume_at",
        value=time.monotonic() - 2.0,
    )
    recovery_calls: list[int] = []

    def _fake_recover(_tray, *, current_brightness: int) -> bool:
        recovery_calls.append(int(current_brightness))
        return True

    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        _fake_recover,
    )

    result = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert recovery_calls == []
    assert result == (0, False)


def test_stable_zero_does_not_fast_recover_outside_restore_window(monkeypatch) -> None:
    """Without a recent restore, a fresh zero read should not recover on the
    first poll — it may be a genuine controller sleep that needs confirmation."""

    tray = _DummyTray(brightness=25, is_off=False)
    tray.config.controller_sleep_respect = True

    recovery_calls: list[int] = []

    def _fake_recover(_tray, *, current_brightness: int) -> bool:
        recovery_calls.append(int(current_brightness))
        return True

    monkeypatch.setattr(
        "keyrgb.tray.pollers.hardware_polling._recover_stable_zero_brightness_best_effort",
        _fake_recover,
    )

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=34,
        last_off_state=False,
    )

    assert recovery_calls == []
    assert (last_brightness, last_off) == (0, False)
