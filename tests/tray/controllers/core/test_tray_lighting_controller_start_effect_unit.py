from __future__ import annotations

from unittest.mock import MagicMock, patch


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestStartCurrentEffect:
    def test_resolve_start_current_effect_policy_rejects_persisted_perkey_without_capability(self):
        from keyrgb.tray.controllers.lighting_controller import _resolve_start_current_effect_policy

        mock_tray = MagicMock()
        mock_tray.backend_caps = None
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 30
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}

        policy = _resolve_start_current_effect_policy(mock_tray, brightness_override=None)

        assert policy.effect == "none"
        assert policy.persist_effect == "none"
        assert policy.start_plan.is_perkey_mode is False
        assert policy.start_plan.is_none_mode is True

    def test_resolve_start_current_effect_policy_keeps_config_unchanged(self):
        from keyrgb.tray.controllers.lighting_controller import _resolve_start_current_effect_policy

        mock_tray = MagicMock()
        mock_tray.config.effect = "none"
        mock_tray.config.brightness = 30

        policy = _resolve_start_current_effect_policy(mock_tray, brightness_override=None)

        assert policy.effect == "none"
        assert policy.persist_effect is None
        assert policy.target_brightness == 30
        assert policy.start_brightness == 30
        assert policy.start_plan.is_none_mode is True
        assert mock_tray.config.effect == "none"

    def test_resolve_start_current_effect_policy_promotes_base_only_state_to_perkey_runtime(self):
        from keyrgb.tray.controllers.lighting_controller import _resolve_start_current_effect_policy

        mock_tray = MagicMock()
        mock_tray.config.effect = "none"
        mock_tray.config.brightness = 30
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}

        policy = _resolve_start_current_effect_policy(mock_tray, brightness_override=None)

        assert policy.effect == "perkey"
        assert policy.persist_effect is None
        assert policy.start_plan.is_perkey_mode is True
        assert policy.start_plan.is_none_mode is False
        assert mock_tray.config.effect == "none"

    def test_resolve_start_current_effect_policy_reports_canonical_effect_persist(self):
        from keyrgb.tray.controllers.lighting_controller import _resolve_start_current_effect_policy

        backend = MagicMock()
        backend.effects.return_value = {"rainbow_wave": object()}

        mock_tray = MagicMock()
        mock_tray.backend = backend
        mock_tray.config.effect = "hw:rainbow_wave"
        mock_tray.config.brightness = 40

        policy = _resolve_start_current_effect_policy(mock_tray, brightness_override=10)

        assert policy.effect == "rainbow_wave"
        assert policy.persist_effect == "rainbow_wave"
        assert policy.target_brightness == 40
        assert policy.start_brightness == 10
        # Policy resolver computes persistence intent but does not mutate config.
        assert mock_tray.config.effect == "hw:rainbow_wave"

    def test_classify_start_current_effect_marks_perkey_static_path(self):
        from keyrgb.tray.controllers.lighting_controller import _classify_start_current_effect

        tray = MagicMock()
        plan = _classify_start_current_effect(tray, effect="perkey")

        assert plan.is_perkey_mode is True
        assert plan.is_none_mode is False
        assert plan.is_loop_effect is False

    def test_classify_start_current_effect_marks_loop_effect(self):
        from keyrgb.tray.controllers.lighting_controller import _classify_start_current_effect

        tray = MagicMock()
        plan = _classify_start_current_effect(tray, effect="rainbow_wave")

        assert plan.is_perkey_mode is False
        assert plan.is_none_mode is False
        assert plan.is_loop_effect is True

    def test_plan_effect_fade_ramp_marks_loop_effect_as_non_hardware(self):
        from keyrgb.tray.controllers.lighting_controller import _plan_effect_fade_ramp

        plan = _plan_effect_fade_ramp(
            effect="rainbow_wave",
            fade_in=True,
            start_brightness=10,
            target_brightness=50,
        )

        assert plan.will_fade is True
        assert plan.is_loop_effect is True
        assert plan.apply_to_hardware is False

    def test_plan_effect_fade_ramp_marks_hardware_effect_as_hardware(self):
        from keyrgb.tray.controllers.lighting_controller import _plan_effect_fade_ramp

        plan = _plan_effect_fade_ramp(
            effect="breathe",
            fade_in=True,
            start_brightness=10,
            target_brightness=50,
        )

        assert plan.will_fade is True
        assert plan.is_loop_effect is False
        assert plan.apply_to_hardware is True

    def test_prepare_effect_engine_state_loads_perkey_for_software_effect(self):
        from keyrgb.tray.controllers import _lighting_effect_coordination

        mock_tray = MagicMock()
        _lighting_effect_coordination.prepare_effect_engine_state(
            mock_tray,
            effect="reactive_ripple",
            is_software_effect_fn=lambda e: e == "reactive_ripple",
            set_engine_perkey_from_config_fn=lambda t: t.engine.mark_sw(),
            clear_engine_perkey_state_fn=lambda t: t.engine.mark_cleared(),
        )

        mock_tray.engine.mark_sw.assert_called_once()
        mock_tray.engine.mark_cleared.assert_not_called()

    def test_prepare_effect_engine_state_clears_perkey_for_hardware_effect(self):
        from keyrgb.tray.controllers import _lighting_effect_coordination

        mock_tray = MagicMock()
        _lighting_effect_coordination.prepare_effect_engine_state(
            mock_tray,
            effect="breathe",
            is_software_effect_fn=lambda e: e == "reactive_ripple",
            set_engine_perkey_from_config_fn=lambda t: t.engine.mark_sw(),
            clear_engine_perkey_state_fn=lambda t: t.engine.mark_cleared(),
        )

        mock_tray.engine.mark_cleared.assert_called_once()
        mock_tray.engine.mark_sw.assert_not_called()

    def test_perkey_turns_off_if_brightness_zero(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 0

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.turn_off.assert_called_once()
        assert mock_tray.is_off is True

    def test_none_effect_calls_set_color(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "none"
        mock_tray.config.brightness = 75
        mock_tray.config.color = (255, 0, 0)
        mock_tray.engine.kb_lock = _lock_mock()

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_color.assert_called_once_with((255, 0, 0), brightness=75)
        assert mock_tray.is_off is False

    def test_none_effect_restores_auxiliary_targets_when_shared_policy_is_enabled(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "none"
        mock_tray.config.brightness = 75
        mock_tray.config.color = (255, 0, 0)
        mock_tray.engine.kb_lock = _lock_mock()
        mock_tray.device_discovery = {
            "candidates": [
                {
                    "device_type": "lightbar",
                    "product": "ITE Device(8233)",
                    "usb_vid": "0x048d",
                    "usb_pid": "0x7001",
                    "status": "supported",
                }
            ]
        }
        mock_tray.secondary_device_controls = {"lightbar:048d:7001": True}
        mock_tray.config.software_effect_target = "all_uniform_capable"

        with patch("keyrgb.tray.controllers.lighting_controller.restore_secondary_software_targets") as restore:
            start_current_effect(mock_tray)

        mock_tray.engine.kb.set_color.assert_called_once_with((255, 0, 0), brightness=75)
        restore.assert_called_once_with(mock_tray)

    def test_animated_effect_starts_engine(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "breathe"
        mock_tray.config.brightness = 100
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        start_current_effect(mock_tray)

        mock_tray.engine.start_effect.assert_called_once_with(
            "breathe",
            speed=3,
            brightness=100,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            reactive_visual_mode="subtle",
            direction=mock_tray.config.direction,
        )
        assert mock_tray.is_off is False
