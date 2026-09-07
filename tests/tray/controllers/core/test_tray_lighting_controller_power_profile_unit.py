from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestPowerSourcePerkeyProfileTransition:
    def test_power_source_perkey_transition_requires_capability_evidence(self):
        from keyrgb.tray.controllers.lighting_controller import apply_power_source_perkey_profile_transition

        mock_tray = MagicMock()
        mock_tray.backend_caps = None

        with patch("keyrgb.tray.controllers.lighting_controller.lighting_mode_apply.apply_perkey_mode") as apply_mode:
            handled = apply_power_source_perkey_profile_transition(mock_tray)

        assert handled is False
        apply_mode.assert_not_called()

    def test_apply_power_source_perkey_profile_transition_updates_perkey_mode_in_place(self):
        from keyrgb.tray.controllers.lighting_controller import apply_power_source_perkey_profile_transition

        mock_tray = MagicMock()
        mock_tray.config.brightness = 25

        with (
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.get_effect_name",
                return_value="perkey",
            ),
            patch("keyrgb.tray.controllers.lighting_controller.lighting_mode_apply.apply_perkey_mode") as apply_mode,
        ):
            handled = apply_power_source_perkey_profile_transition(mock_tray)

        assert handled is True
        apply_mode.assert_called_once_with(mock_tray, brightness_override=25, reassert_user_mode=False)

    def test_apply_power_source_perkey_profile_transition_updates_software_effect_in_place(self):
        from keyrgb.tray.controllers.lighting_controller import apply_power_source_perkey_profile_transition

        mock_tray = MagicMock()
        mock_tray.is_off = True
        mock_tray.config.brightness = 10

        with (
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.get_effect_name",
                return_value="reactive_ripple",
            ),
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.is_software_effect",
                return_value=True,
            ),
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.set_engine_perkey_from_config_for_sw_effect"
            ) as set_sw_state,
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_mode_apply.restore_hidden_perkey_rows_from_recovery_hint"
            ) as hidden_restore,
        ):
            handled = apply_power_source_perkey_profile_transition(mock_tray)

        assert handled is True
        assert mock_tray.is_off is False
        set_sw_state.assert_called_once_with(mock_tray)
        hidden_restore.assert_called_once_with(mock_tray, brightness_override=10)

    def test_apply_power_source_perkey_profile_transition_uses_live_engine_effect_before_config_perkey(self):
        from keyrgb.tray.controllers.lighting_controller import apply_power_source_perkey_profile_transition

        mock_tray = MagicMock()
        mock_tray.is_off = True
        mock_tray.engine.current_effect = "reactive_ripple"
        mock_tray.config.effect = "perkey"

        with (
            patch("keyrgb.tray.controllers.lighting_controller.lighting_mode_apply.apply_perkey_mode") as apply_mode,
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.set_engine_perkey_from_config_for_sw_effect"
            ) as set_sw_state,
        ):
            handled = apply_power_source_perkey_profile_transition(mock_tray)

        assert handled is True
        assert mock_tray.is_off is False
        apply_mode.assert_not_called()
        set_sw_state.assert_called_once_with(mock_tray)

    def test_apply_power_source_perkey_profile_transition_returns_false_for_nonsoftware_effect(self):
        from keyrgb.tray.controllers.lighting_controller import apply_power_source_perkey_profile_transition

        mock_tray = MagicMock()

        with (
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.get_effect_name",
                return_value="breathing",
            ),
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.is_software_effect",
                return_value=False,
            ),
            patch("keyrgb.tray.controllers.lighting_controller.lighting_mode_apply.apply_perkey_mode") as apply_mode,
            patch(
                "keyrgb.tray.controllers.lighting_controller.lighting_controller_helpers.set_engine_perkey_from_config_for_sw_effect"
            ) as set_sw_state,
        ):
            handled = apply_power_source_perkey_profile_transition(mock_tray)

        assert handled is False
        apply_mode.assert_not_called()
        set_sw_state.assert_not_called()
