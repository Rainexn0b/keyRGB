from __future__ import annotations

from unittest.mock import MagicMock, patch


def _mk_tray(*, effect: str, brightness: int = 50) -> MagicMock:
    tray = MagicMock()
    tray.is_off = False
    tray._user_forced_off = False
    tray._idle_forced_off = False
    tray._power_forced_off = False
    tray.config.effect = effect
    tray.config.brightness = brightness
    return tray


class TestApplyBrightnessFromPowerPolicy:
    def test_apply_brightness_from_power_policy_restarts_non_software_effect(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="breathe")

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.brightness == 25
        mock_tray.engine.set_brightness.assert_called_once_with(
            25, apply_to_hardware=True, fade=True, fade_duration_s=0.25
        )
        mock_start.assert_called_once_with(mock_tray)

    def test_apply_brightness_from_power_policy_does_not_restart_software_effect(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="rainbow_wave")

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.brightness == 25
        mock_tray.engine.set_brightness.assert_called_once_with(
            25,
            apply_to_hardware=False,
            fade=True,
            fade_duration_s=0.25,
        )
        mock_start.assert_not_called()

    def test_apply_brightness_from_power_policy_updates_perkey_brightness_for_reactive_effect(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="reactive_ripple", brightness=200)
        mock_tray.config.perkey_brightness = 50

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.perkey_brightness == 25
        assert mock_tray.config.brightness == 25
        mock_tray.engine.set_brightness.assert_called_once_with(
            25, apply_to_hardware=False, fade=True, fade_duration_s=0.25
        )
        mock_start.assert_not_called()

    def test_apply_brightness_from_power_policy_logs_reactive_engine_failure_but_keeps_ui_flow(self):
        from src.tray.controllers._power import _lighting_power_policy as power_policy_module
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="reactive_ripple", brightness=200)
        mock_tray.config.perkey_brightness = 50
        mock_tray.engine.set_brightness.side_effect = RuntimeError("engine failed")
        logs = []

        with (
            patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start,
            patch.object(
                power_policy_module,
                "_log_tray_exception",
                side_effect=lambda _tray, msg, exc: logs.append((msg, exc)),
            ),
        ):
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.perkey_brightness == 25
        assert mock_tray.config.brightness == 25
        mock_tray.engine.set_brightness.assert_called_once_with(
            25, apply_to_hardware=False, fade=True, fade_duration_s=0.25
        )
        mock_tray._refresh_ui.assert_called_once_with()
        mock_start.assert_not_called()
        assert len(logs) == 1
        assert logs[0][0] == "Failed to apply reactive power-policy brightness: %s"
        assert isinstance(logs[0][1], RuntimeError)

    def test_apply_brightness_from_power_policy_logs_outer_boundary_failure_without_raising(self):
        from src.tray.controllers._power import _lighting_power_policy as power_policy_module
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="breathe")
        mock_tray._refresh_ui.side_effect = LookupError("ui failed")
        logs = []

        with (
            patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start,
            patch.object(
                power_policy_module,
                "_log_tray_exception",
                side_effect=lambda _tray, msg, exc: logs.append((msg, exc)),
            ),
        ):
            apply_brightness_from_power_policy(mock_tray, 25)

        mock_start.assert_called_once_with(mock_tray)
        assert len(logs) == 1
        assert logs[0][0] == "Failed to apply tray lighting power-policy brightness: %s"
        assert isinstance(logs[0][1], LookupError)
