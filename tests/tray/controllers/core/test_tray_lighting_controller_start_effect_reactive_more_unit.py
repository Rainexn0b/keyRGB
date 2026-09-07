from __future__ import annotations

from unittest.mock import MagicMock


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestStartCurrentEffectReactiveMore:
    def test_perkey_effect_calls_set_key_colors(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 50
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.enable_user_mode = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()

        start_current_effect(mock_tray, controller_brightness_handoff=50)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_key_colors.assert_called_once()
        assert mock_tray.is_off is False

    def test_reactive_effect_forwards_controller_brightness_handoff(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "reactive_ripple"
        mock_tray.config.brightness = 40
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        mock_tray.config.reactive_visual_mode = "subtle"

        start_current_effect(mock_tray, controller_brightness_handoff=50)

        mock_tray.engine.start_effect.assert_called_once_with(
            "reactive_ripple",
            speed=3,
            brightness=40,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            reactive_visual_mode="subtle",
            direction=mock_tray.config.direction,
            controller_brightness_handoff=50,
        )

    def test_perkey_in_place_apply_skips_user_mode_reassertion(self):
        from keyrgb.tray.controllers import _lighting_mode_apply as helpers

        mock_tray = MagicMock()
        mock_tray.config.brightness = 35
        mock_tray.config.perkey_brightness = 35
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.enable_user_mode = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()

        helpers.apply_perkey_mode(mock_tray, reassert_user_mode=False)

        mock_tray.engine.stop.assert_not_called()
        mock_tray.engine.kb.enable_user_mode.assert_not_called()
        mock_tray.engine.kb.set_key_colors.assert_called_once_with(
            mock_tray.config.per_key_colors,
            brightness=35,
            enable_user_mode=False,
        )
        assert mock_tray.is_off is False

    def test_perkey_in_place_apply_reasserts_when_backend_requires_it(self):
        from keyrgb.tray.controllers import _lighting_mode_apply as helpers

        mock_tray = MagicMock()
        mock_tray.config.brightness = 35
        mock_tray.config.perkey_brightness = 35
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.keyrgb_per_key_mode_policy = "reassert_every_frame"
        mock_tray.engine.kb.enable_user_mode = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()

        helpers.apply_perkey_mode(mock_tray, reassert_user_mode=False)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.enable_user_mode.assert_not_called()
        mock_tray.engine.kb.set_key_colors.assert_called_once_with(
            mock_tray.config.per_key_colors,
            brightness=35,
            enable_user_mode=True,
        )
        assert mock_tray.is_off is False

    def test_perkey_in_place_apply_reuses_hidden_blank_without_user_mode_reassert(self):
        from keyrgb.tray.controllers import _lighting_mode_apply as helpers

        mock_tray = MagicMock()
        mock_tray.config.brightness = 35
        mock_tray.config.perkey_brightness = 35
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.keyrgb_per_key_mode_policy = "reassert_every_frame"
        mock_tray.engine.kb.get_brightness = MagicMock(return_value=0)
        mock_tray.engine.kb.is_off = MagicMock(return_value=False)
        mock_tray.engine.kb.set_brightness = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()

        helpers.apply_perkey_mode(mock_tray, reassert_user_mode=False)

        mock_tray.engine.stop.assert_not_called()
        mock_tray.engine.kb.set_key_colors.assert_called_once_with(
            mock_tray.config.per_key_colors,
            brightness=35,
            enable_user_mode=False,
        )
        mock_tray.engine.kb.set_brightness.assert_called_once_with(35)
        assert mock_tray.is_off is False

    def test_reactive_blank_recovery_restores_hidden_rows_without_user_mode_or_restart(self, monkeypatch):
        # Opt out of the default-on recovery user-mode save so this test stays
        # scoped to the hidden-row restore contract (covered separately).
        monkeypatch.setenv("KEYRGB_RECOVERY_USER_MODE_SAVE", "0")
        from keyrgb.tray.controllers import _lighting_mode_apply as helpers
        from keyrgb.tray.idle_power_state import set_idle_power_state_field

        mock_tray = MagicMock()
        mock_tray.config.brightness = 10
        mock_tray.config.per_key_colors = {(0, 0): (0, 255, 255)}
        mock_tray.engine.kb.get_brightness = MagicMock(side_effect=AssertionError("should use hint"))
        mock_tray.engine.kb.is_off = MagicMock(side_effect=AssertionError("should use hint"))
        mock_tray.engine.kb.enable_user_mode = MagicMock(side_effect=AssertionError("must not reinitialize"))
        mock_tray.engine.kb.set_brightness = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()
        set_idle_power_state_field(
            mock_tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=0,
        )
        set_idle_power_state_field(
            mock_tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=False,
        )

        restored = helpers.restore_hidden_perkey_rows_from_recovery_hint(mock_tray)

        assert restored is True
        mock_tray.engine.stop.assert_not_called()
        mock_tray.engine.kb.enable_user_mode.assert_not_called()
        mock_tray.engine.kb.set_key_colors.assert_called_once_with(
            mock_tray.config.per_key_colors,
            brightness=10,
            enable_user_mode=False,
        )
        mock_tray.engine.kb.set_brightness.assert_called_once_with(10)

    def test_perkey_in_place_apply_uses_hardware_blank_hints_without_requery(self):
        from keyrgb.tray.controllers import _lighting_mode_apply as helpers
        from keyrgb.tray.idle_power_state import set_idle_power_state_field

        mock_tray = MagicMock()
        mock_tray.config.brightness = 35
        mock_tray.config.perkey_brightness = 35
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.keyrgb_per_key_mode_policy = "reassert_every_frame"
        mock_tray.engine.kb.get_brightness = MagicMock(side_effect=AssertionError("should use hint"))
        mock_tray.engine.kb.is_off = MagicMock(side_effect=AssertionError("should use hint"))
        mock_tray.engine.kb.set_brightness = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()
        set_idle_power_state_field(
            mock_tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=0,
        )
        set_idle_power_state_field(
            mock_tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=False,
        )

        helpers.apply_perkey_mode(mock_tray, reassert_user_mode=False)

        mock_tray.engine.stop.assert_not_called()
        mock_tray.engine.kb.set_key_colors.assert_called_once_with(
            mock_tray.config.per_key_colors,
            brightness=35,
            enable_user_mode=False,
        )
        mock_tray.engine.kb.set_brightness.assert_called_once_with(35)
        assert not hasattr(mock_tray, "_hidden_perkey_restore_brightness_hint")
        assert not hasattr(mock_tray, "_hidden_perkey_restore_device_off_hint")
        assert mock_tray.tray_idle_power_state.hidden_perkey_restore_brightness_hint is None
        assert mock_tray.tray_idle_power_state.hidden_perkey_restore_device_off_hint is None
        assert mock_tray.is_off is False
