from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.tray.controllers._transition_constants import (
    SOFT_OFF_FADE_DURATION_S,
    SOFT_ON_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
)


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestTurnOffOn:
    def test_turn_off_sets_flags_and_calls_engine(self):
        from src.tray.controllers.lighting_controller import turn_off

        mock_tray = MagicMock()
        mock_tray.is_off = False

        turn_off(mock_tray)

        assert mock_tray._user_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once()
        mock_tray._refresh_ui.assert_called_once()

    def test_turn_on_clears_flags_and_restores_brightness(self):
        from src.tray.controllers.lighting_controller import turn_on

        mock_tray = MagicMock()
        mock_tray.is_off = True
        mock_tray.config.brightness = 0
        mock_tray._last_brightness = 75
        mock_tray.config.effect = "breathe"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray._user_forced_off is False
        assert mock_tray._idle_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 75
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )

    def test_turn_on_uses_default_25_if_no_last_brightness(self):
        from src.tray.controllers.lighting_controller import turn_on

        mock_tray = MagicMock()
        mock_tray.is_off = True
        mock_tray.config.brightness = 0
        mock_tray._last_brightness = 0
        mock_tray.config.effect = "none"
        mock_tray.config.color = (255, 255, 255)
        mock_tray.engine.kb_lock = _lock_mock()

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray.config.brightness == 25
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )


class TestPowerTurnOffRestore:
    def test_power_turn_off_sets_power_forced_flag(self):
        from src.tray.controllers.lighting_controller import power_turn_off

        mock_tray = MagicMock()
        mock_tray.is_off = False

        power_turn_off(mock_tray)

        assert mock_tray._power_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once_with(
            fade=True,
            fade_duration_s=SOFT_OFF_FADE_DURATION_S,
        )

    def test_power_restore_restores_when_power_forced(self):
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._user_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = True
        mock_tray.is_off = True
        mock_tray.config.brightness = 0
        mock_tray._last_brightness = 50
        mock_tray.config.effect = "breathe"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        assert mock_tray._power_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 50
        assert mock_tray.engine.current_color == (0, 0, 0)
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )

    def test_power_restore_restores_when_off_due_to_hardware_reset(self):
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._power_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._user_forced_off = False
        mock_tray.is_off = True
        mock_tray.config.brightness = 25
        mock_tray.config.effect = "none"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        assert mock_tray.is_off is False
        assert mock_tray.engine.current_color == (0, 0, 0)
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )

    def test_power_restore_does_not_fight_user_forced_off(self):
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._user_forced_off = True
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = False
        mock_tray.is_off = True
        mock_tray.config.brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        mock_start.assert_not_called()
