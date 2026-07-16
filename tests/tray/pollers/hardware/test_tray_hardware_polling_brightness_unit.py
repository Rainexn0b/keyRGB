from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from src.tray.pollers.hardware_polling import _apply_polled_hardware_state


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


def test_hardware_polling_does_not_mark_off_from_zero_brightness_without_off_state() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is False

    # Config brightness is user intent / last chosen brightness and should not
    # be overwritten by transient hardware reads of 0.
    assert tray.config.brightness == 25
    assert tray.is_off is False
    assert tray.refresh_count == 0


def test_hardware_polling_marks_off_when_zero_brightness_matches_off_state() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=True,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is True
    assert tray.config.brightness == 25
    assert tray.is_off is True
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_does_not_persist_nonzero_brightness_and_clears_off() -> None:
    tray = _DummyTray(brightness=25, is_off=True)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=15,
        current_off=False,
        last_brightness=0,
        last_off_state=True,
    )

    assert last_brightness == 15
    assert last_off is False
    # Brightness reads from hardware should not overwrite the user's persisted
    # tray selection.
    assert tray.config.brightness == 25
    assert tray.is_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_ignores_forced_off_zero_changes() -> None:
    tray = _DummyTray(brightness=25, is_off=True, power_forced_off=True)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=0,
        current_off=True,
        last_brightness=25,
        last_off_state=False,
    )

    assert last_brightness == 0
    assert last_off is True

    # Don't fight forced-off state; also do not refresh.
    assert tray.config.brightness == 25
    assert tray.refresh_count == 0


def test_hardware_polling_does_not_convert_small_brightness_values() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=7,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    # No scale conversion; value is used as-is (within 0..50 range).
    assert last_brightness == 7
    assert last_off is False
    # But do not persist into config.
    assert tray.config.brightness == 25
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_clamps_over_50_brightness_values() -> None:
    tray = _DummyTray(brightness=25, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=80,
        current_off=False,
        last_brightness=25,
        last_off_state=False,
    )

    # No scale conversion; clamp into 0..50.
    assert last_brightness == 50
    assert last_off is False


def test_hardware_polling_does_not_scale_up_when_config_expects_low_value() -> None:
    """Regression: values 1..10 can be valid on the 0..50 scale.

    If the backend reports 10 and the config is already 10, we must not treat it
    as a 0..10 scale value and rewrite it to 50.
    """

    tray = _DummyTray(brightness=10, is_off=False)

    last_brightness, last_off = _apply_polled_hardware_state(
        tray,
        current_brightness=10,
        current_off=False,
        last_brightness=15,
        last_off_state=False,
    )

    assert tray.config.brightness == 10
    assert last_brightness == 10
    assert last_off is False
    assert tray.refresh_count == 1
    assert tray.last_animate_icon is False


def test_hardware_polling_recovers_recent_power_source_blank_without_marking_off(monkeypatch) -> None:
    tray = _DummyTray(brightness=25, is_off=False)
    tray._last_power_source_transition_at = 100.0
    tray._apply_power_source_perkey_profile_transition = MagicMock(return_value=True)

    monkeypatch.setattr("src.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

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

    monkeypatch.setattr("src.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

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

    monkeypatch.setattr("src.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

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

    monkeypatch.setattr("src.tray.pollers.hardware_polling.time.monotonic", lambda: 200.0)

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

    monkeypatch.setattr("src.tray.pollers.hardware_polling.time.monotonic", lambda: 101.0)

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
