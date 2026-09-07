from __future__ import annotations

import threading
from unittest.mock import MagicMock

from keyrgb.core.effects.reactive import _render_brightness_support as reactive_support


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestStartCurrentEffectReactive:
    def test_start_current_effect_fade_for_loop_effect_uses_non_hardware_brightness_write(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "rainbow_wave"
        mock_tray.config.brightness = 50
        mock_tray.config.perkey_brightness = 50
        mock_tray.config.per_key_colors = {}
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        mock_tray.config.reactive_visual_mode = "subtle"
        mock_tray.config.reactive_visual_mode = "subtle"
        reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness = False
        mock_tray.engine.reactive_brightness = 50
        mock_tray.engine.per_key_brightness = 50

        def _assert_fade_state(*args, **kwargs):
            assert reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness is True
            assert mock_tray.engine.reactive_brightness == 50
            assert mock_tray.engine.per_key_brightness == 50

        mock_tray.engine.set_brightness.side_effect = _assert_fade_state

        start_current_effect(mock_tray, brightness_override=10, fade_in=True, fade_in_duration_s=0.42)

        mock_tray.engine.start_effect.assert_called_once_with(
            "rainbow_wave",
            speed=3,
            brightness=10,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            reactive_visual_mode="subtle",
            direction=mock_tray.config.direction,
        )
        mock_tray.engine.set_brightness.assert_called_once_with(
            50,
            apply_to_hardware=False,
            fade=True,
            fade_duration_s=0.42,
        )
        assert reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness is False
        assert mock_tray.engine.reactive_brightness == 50
        assert mock_tray.engine.per_key_brightness == 50

    def test_start_current_effect_forwards_config_restart_brightness_preservation(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "rainbow_wave"
        mock_tray.config.brightness = 40
        mock_tray.config.perkey_brightness = 40
        mock_tray.config.per_key_colors = {}
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        mock_tray.config.reactive_visual_mode = "subtle"

        start_current_effect(mock_tray, preserve_last_rendered_brightness=True)

        assert mock_tray.engine.start_effect.call_args.kwargs["preserve_last_rendered_brightness"] is True

    def test_start_current_effect_idle_restore_loop_effect_fades_with_follow_global_cap(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect
        from keyrgb.tray.idle_power_state import set_idle_power_state_field

        mock_tray = MagicMock()
        set_idle_power_state_field(
            mock_tray,
            attr_name="_idle_restore_loop_effect_ramp",
            state_name="idle_restore_loop_effect_ramp",
            value=True,
        )
        mock_tray.config.effect = "rainbow_wave"
        mock_tray.config.brightness = 50
        mock_tray.config.perkey_brightness = 50
        mock_tray.config.per_key_colors = {}
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        mock_tray.config.reactive_visual_mode = "subtle"
        reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness = False
        mock_tray.engine.reactive_brightness = 50
        mock_tray.engine.per_key_brightness = 50

        follow_global_during_fade: list[bool] = []

        def _capture_set_brightness(*args, **kwargs):
            follow_global_during_fade.append(
                bool(reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness)
            )

        mock_tray.engine.set_brightness.side_effect = _capture_set_brightness

        start_current_effect(mock_tray, brightness_override=10, fade_in=True, fade_in_duration_s=0.42)

        mock_tray.engine.start_effect.assert_called_once_with(
            "rainbow_wave",
            speed=3,
            brightness=10,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            reactive_visual_mode="subtle",
            direction=mock_tray.config.direction,
        )
        mock_tray.engine.set_brightness.assert_called_once_with(
            50,
            apply_to_hardware=False,
            fade=True,
            fade_duration_s=0.42,
        )
        # The follow-global cap is active while the ramp runs so reactive
        # base/effect brightness cannot outrun the fading global level...
        assert follow_global_during_fade == [True]
        # ...and is always cleared afterwards.
        assert reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness is False
        assert mock_tray.engine.reactive_brightness == 50
        assert mock_tray.engine.per_key_brightness == 50

    def test_idle_restore_releases_reactive_target_after_global_fade(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect
        from keyrgb.tray.idle_power_state import set_idle_power_state_field

        mock_tray = MagicMock()
        set_idle_power_state_field(
            mock_tray,
            attr_name="_idle_restore_loop_effect_ramp",
            state_name="idle_restore_loop_effect_ramp",
            value=True,
        )
        mock_tray.config.effect = "reactive_ripple"
        mock_tray.config.brightness = 10
        mock_tray.config.perkey_brightness = 50
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        mock_tray.config.reactive_visual_mode = "subtle"
        mock_tray.engine.reactive_lock = None
        mock_tray.engine._start_lock = threading.RLock()
        mock_tray.engine._thread_generation = 7
        mock_tray.engine.reactive_brightness = 50
        mock_tray.engine.per_key_brightness = 50

        start_current_effect(mock_tray, brightness_override=1, fade_in=True, fade_in_duration_s=0.42)

        state = reactive_support.ensure_reactive_state(mock_tray.engine)
        assert state._reactive_follow_global_brightness is False
        assert state._reactive_transition_from_brightness == 10
        assert state._reactive_transition_to_brightness == 50
        assert state._reactive_transition_duration_s == 0.42
        assert state._reactive_transition_started_at is not None

    def test_superseded_idle_fade_does_not_seed_replacement_effect(self):
        from keyrgb.core.effects.reactive._render_brightness_support import ReactiveRenderState
        from keyrgb.tray.controllers._lighting_effect_coordination import (
            _apply_effect_fade_ramp,
            _FadeRampPlan,
        )
        from keyrgb.tray.idle_power_state import set_idle_power_state_field

        mock_tray = MagicMock()
        set_idle_power_state_field(
            mock_tray,
            attr_name="_idle_restore_loop_effect_ramp",
            state_name="idle_restore_loop_effect_ramp",
            value=True,
        )
        mock_tray.engine.reactive_lock = None
        mock_tray.engine._start_lock = threading.RLock()
        mock_tray.engine._thread_generation = 7
        mock_tray.engine.brightness = 1
        mock_tray.engine.reactive_brightness = 50
        mock_tray.engine.per_key_brightness = 10
        mock_tray.engine.per_key_colors = {(0, 0): (0, 0, 0)}

        def _supersede_fade(*_args, **_kwargs):
            mock_tray.engine._thread_generation = 8
            mock_tray.engine._reactive_state = ReactiveRenderState()

        mock_tray.engine.set_brightness.side_effect = _supersede_fade

        _apply_effect_fade_ramp(
            mock_tray,
            plan=_FadeRampPlan(will_fade=True, is_loop_effect=True, apply_to_hardware=False),
            target_brightness=10,
            start_brightness=1,
            fade_in_duration_s=0.42,
        )

        state = reactive_support.ensure_reactive_state(mock_tray.engine)
        assert state._reactive_follow_global_brightness is False
        assert state._reactive_transition_from_brightness is None
        assert state._reactive_transition_to_brightness is None

    def test_post_fade_release_ignores_inactive_per_key_target(self):
        from keyrgb.tray.controllers._lighting_effect_coordination import (
            _seed_post_fade_reactive_release,
        )

        mock_tray = MagicMock()
        mock_tray.engine.reactive_lock = None
        mock_tray.engine.reactive_brightness = 20
        mock_tray.engine.per_key_brightness = 50
        mock_tray.engine.per_key_colors = {}

        _seed_post_fade_reactive_release(mock_tray, from_brightness=10, duration_s=0.42)

        state = reactive_support.ensure_reactive_state(mock_tray.engine)
        assert state._reactive_transition_from_brightness == 10
        assert state._reactive_transition_to_brightness == 20

    def test_start_current_effect_fade_for_hardware_effect_uses_hardware_fade(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "breathe"
        mock_tray.config.brightness = 50
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        mock_tray.config.reactive_visual_mode = "subtle"

        start_current_effect(mock_tray, brightness_override=10, fade_in=True, fade_in_duration_s=0.42)

        mock_tray.engine.start_effect.assert_called_once_with(
            "breathe",
            speed=3,
            brightness=10,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            reactive_visual_mode="subtle",
            direction=mock_tray.config.direction,
        )
        mock_tray.engine.set_brightness.assert_called_once_with(
            50,
            apply_to_hardware=True,
            fade=True,
            fade_duration_s=0.42,
        )
