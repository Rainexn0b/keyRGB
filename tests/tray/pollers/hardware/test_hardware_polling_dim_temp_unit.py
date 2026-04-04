from __future__ import annotations

from unittest.mock import MagicMock

from src.tray.pollers.hardware_polling import _apply_polled_hardware_state


def test_hardware_polling_dim_temp_target_does_not_refresh_or_toggle_off() -> None:
    tray = MagicMock()
    tray._dim_temp_active = True
    tray._dim_temp_target_brightness = 5
    tray._power_forced_off = False
    tray._user_forced_off = False
    tray._idle_forced_off = False
    tray.is_off = False

    new_last_brightness, new_last_off = _apply_polled_hardware_state(
        tray,
        raw_brightness=5,
        current_brightness=5,
        current_off=False,
        last_brightness=10,
        last_off_state=None,
    )

    assert new_last_brightness == 5
    assert new_last_off is False
    assert tray.is_off is False
    tray._refresh_ui.assert_not_called()


def test_hardware_polling_never_clears_is_off_when_user_forced_off() -> None:
    tray = MagicMock()
    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    tray._power_forced_off = False
    tray._user_forced_off = True
    tray._idle_forced_off = False
    tray.is_off = True

    _apply_polled_hardware_state(
        tray,
        raw_brightness=10,
        current_brightness=10,
        current_off=False,
        last_brightness=0,
        last_off_state=None,
    )

    assert tray.is_off is True


def test_hardware_polling_can_clear_is_off_when_not_forced_off() -> None:
    tray = MagicMock()
    tray._dim_temp_active = False
    tray._dim_temp_target_brightness = None
    tray._power_forced_off = False
    tray._user_forced_off = False
    tray._idle_forced_off = False
    tray.is_off = True

    _apply_polled_hardware_state(
        tray,
        raw_brightness=10,
        current_brightness=10,
        current_off=False,
        last_brightness=0,
        last_off_state=None,
    )

    assert tray.is_off is False
