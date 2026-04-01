from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestOnSpeedClicked:
    def test_on_speed_clicked_updates_config_and_restarts_effect(self):
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.speed = 1
        mock_tray.config.effect = "breathe"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "🔘 5")

        assert mock_tray.config.speed == 5
        mock_start.assert_called_once_with(mock_tray)
        mock_tray._update_menu.assert_called_once()

    def test_on_speed_clicked_skips_restart_if_off(self):
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = True

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "3")

        assert mock_tray.config.speed == 3
        mock_start.assert_not_called()

    def test_on_speed_clicked_ignores_invalid_input(self):
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        original_speed = mock_tray.config.speed

        on_speed_clicked(mock_tray, "not a number")

        assert mock_tray.config.speed == original_speed

    def test_on_speed_clicked_sw_effect_updates_engine_speed_without_restart(self):
        """For software effects, speed change should update engine.speed in-place, not restart."""
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        # Use a known software effect name from the catalog.
        mock_tray.config.effect = "rainbow_wave"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "8")

        assert mock_tray.config.speed == 8
        # Engine speed is updated in-place.
        assert mock_tray.engine.speed == 8
        # Per-effect speed is persisted.
        mock_tray.config.set_effect_speed.assert_called_once_with("rainbow_wave", 8)
        # Full restart is NOT issued (avoids flicker).
        mock_start.assert_not_called()

    def test_on_speed_clicked_hw_effect_still_restarts(self):
        """For hardware effects, speed change still requires a full effect restart."""
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        # Use a known hardware effect name that is NOT in SW_EFFECTS_SET.
        mock_tray.config.effect = "breathing"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "6")

        assert mock_tray.config.speed == 6
        mock_start.assert_called_once_with(mock_tray)

    def test_on_speed_clicked_logs_and_restarts_if_inplace_update_fails(self):
        from src.tray.controllers.lighting_controller import on_speed_clicked

        class BrokenSpeedEngine:
            def __init__(self) -> None:
                self._speed = 0

            @property
            def speed(self) -> int:
                return self._speed

            @speed.setter
            def speed(self, value: int) -> None:
                raise RuntimeError("cannot set speed")

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.effect = "rainbow_wave"
        mock_tray.engine = BrokenSpeedEngine()

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "7")

        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args[0][0] == "Failed to update engine speed in place: %s"
        assert str(mock_tray._log_exception.call_args[0][1]) == "cannot set speed"
        mock_start.assert_called_once_with(mock_tray)
        mock_tray._update_menu.assert_called_once()

class TestOnBrightnessClicked:
    def test_on_brightness_clicked_updates_config_and_restarts(self):
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_brightness_clicked(mock_tray, "🔘 20")

        assert mock_tray.config.brightness == 100
        mock_tray.engine.set_brightness.assert_called_once_with(100, apply_to_hardware=True)
        mock_start.assert_called_once_with(mock_tray)

    def test_on_brightness_clicked_does_not_restart_software_effect(self):
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.effect = "rainbow_wave"
        mock_tray.config.brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_brightness_clicked(mock_tray, "🔘 20")

        assert mock_tray.config.brightness == 100
        mock_tray.engine.set_brightness.assert_called_once_with(100, apply_to_hardware=False)
        mock_start.assert_not_called()

    def test_on_brightness_clicked_updates_perkey_brightness_for_reactive_effect(self):
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.effect = "reactive_fade"
        mock_tray.config.brightness = 25
        mock_tray.config.reactive_brightness = 25
        mock_tray.config.perkey_brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_brightness_clicked(mock_tray, "🔘 20")

        assert mock_tray.config.brightness == 100
        assert mock_tray.config.reactive_brightness == 100
        mock_tray.engine.set_brightness.assert_called_once_with(100, apply_to_hardware=False)
        mock_start.assert_not_called()

    def test_on_brightness_clicked_saves_nonzero_to_last_brightness(self):
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray._last_brightness = 50

        with patch("src.tray.controllers.lighting_controller.start_current_effect"):
            on_brightness_clicked(mock_tray, "15")

        assert mock_tray._last_brightness == 75

    def test_on_brightness_clicked_does_not_save_zero_to_last_brightness(self):
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray._last_brightness = 100

        with patch("src.tray.controllers.lighting_controller.start_current_effect"):
            on_brightness_clicked(mock_tray, "0")

        assert mock_tray._last_brightness == 100
