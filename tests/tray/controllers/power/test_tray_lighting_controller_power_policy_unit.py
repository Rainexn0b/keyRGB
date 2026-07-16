from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def _mk_tray(*, effect: str, brightness: int = 50) -> MagicMock:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(is_off=False)
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

    def test_apply_brightness_from_power_policy_preserves_reactive_brightness_for_reactive_effect(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="reactive_ripple", brightness=200)
        mock_tray.config.perkey_brightness = 50
        mock_tray.config.reactive_brightness = 40
        mock_tray.engine.reactive_brightness = 40

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.perkey_brightness == 25
        assert mock_tray.config.brightness == 25
        assert mock_tray.config.reactive_brightness == 40
        assert mock_tray.engine.per_key_brightness == 25
        assert mock_tray.engine.reactive_brightness == 40
        mock_tray.engine.set_brightness.assert_called_once_with(
            25, apply_to_hardware=False, fade=True, fade_duration_s=0.25
        )
        mock_start.assert_not_called()

    def test_apply_brightness_from_power_policy_updates_perkey_mode_in_place_without_restart(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="perkey", brightness=40)
        mock_tray.config.perkey_brightness = 40

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 20)

        assert mock_tray.config.brightness == 20
        assert mock_tray.config.perkey_brightness == 20
        assert mock_tray.engine.per_key_brightness == 20
        mock_tray.engine.set_brightness.assert_called_once_with(
            20,
            apply_to_hardware=True,
            fade=True,
            fade_duration_s=0.25,
        )
        mock_start.assert_not_called()

    def test_apply_brightness_from_power_policy_updates_base_only_perkey_runtime_without_restart(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="none", brightness=40)
        mock_tray.config.perkey_brightness = 40
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 18)

        assert mock_tray.config.brightness == 18
        assert mock_tray.config.perkey_brightness == 18
        assert mock_tray.engine.per_key_brightness == 18
        mock_tray.engine.set_brightness.assert_called_once_with(
            18,
            apply_to_hardware=True,
            fade=True,
            fade_duration_s=0.25,
        )
        mock_start.assert_not_called()

    def test_apply_brightness_from_power_policy_logs_reactive_engine_failure_but_keeps_ui_flow(self):
        from src.tray.controllers import _lighting_controller_helpers as helper_module
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="reactive_ripple", brightness=200)
        mock_tray.config.perkey_brightness = 50
        mock_tray.config.reactive_brightness = 40
        mock_tray.engine.reactive_brightness = 40
        mock_tray.engine.set_brightness.side_effect = RuntimeError("engine failed")
        logs = []

        with (
            patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start,
            patch.object(
                helper_module,
                "_log_tray_exception",
                side_effect=lambda _tray, msg, exc: logs.append((msg, exc)),
            ),
        ):
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.perkey_brightness == 25
        assert mock_tray.config.brightness == 25
        assert mock_tray.config.reactive_brightness == 40
        assert mock_tray.engine.per_key_brightness == 25
        assert mock_tray.engine.reactive_brightness == 40
        mock_tray.engine.set_brightness.assert_called_once_with(
            25, apply_to_hardware=False, fade=True, fade_duration_s=0.25
        )
        mock_tray._refresh_ui.assert_called_once_with()
        mock_start.assert_not_called()
        assert len(logs) == 1
        assert logs[0][0] == "Failed to apply power policy reactive brightness: %s"
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

    def test_apply_brightness_from_power_policy_propagates_unexpected_outer_boundary_failure(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = _mk_tray(effect="breathe")
        mock_tray._refresh_ui.side_effect = AssertionError("unexpected power-policy bug")

        with pytest.raises(AssertionError, match="unexpected power-policy bug"):
            apply_brightness_from_power_policy(mock_tray, 25)
