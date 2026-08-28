from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from keyrgb.tray.controllers._power._transition_constants import (
    DEFAULT_IDLE_FADE_DURATION_S,
    SOFT_ON_START_BRIGHTNESS,
    idle_fade_duration_s,
)


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestTurnOffOn:
    def test_turn_off_sets_flags_and_calls_engine(self):
        from keyrgb.tray.controllers.lighting_controller import turn_off
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=False)

        turn_off(mock_tray)

        assert mock_tray._user_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.tray_idle_power_state.user_forced_off is True
        assert mock_tray.tray_idle_power_state.idle_forced_off is False
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once()
        mock_tray._refresh_ui.assert_called_once()

    def test_turn_on_clears_flags_and_restores_brightness(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=True, last_brightness=75)
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "breathe"
        mock_tray.tray_idle_power_state.last_resume_at = 0.0

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray._user_forced_off is False
        assert mock_tray._idle_forced_off is False
        assert mock_tray.tray_idle_power_state.user_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 75
        assert float(mock_tray.tray_idle_power_state.last_resume_at) > 0.0
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_turn_on_uses_default_25_if_no_last_brightness(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=True, last_brightness=0)
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "none"
        mock_tray.config.color = (255, 255, 255)
        mock_tray.engine.kb_lock = _lock_mock()

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray.config.brightness == 25
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )


class TestPowerTurnOffRestore:
    def test_normalize_restore_policy_short_circuits_on_user_forced_off(self):
        from keyrgb.tray._power_restore_policy import normalize_lighting_power_restore_policy_state
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        idle_sentinel = object()
        power_sentinel = object()
        tray = SimpleNamespace(
            _user_forced_off=True,
            _idle_forced_off=idle_sentinel,
            _power_forced_off=power_sentinel,
            tray_idle_power_state=TrayIdlePowerState(
                user_forced_off=True,
                idle_forced_off=False,
                power_forced_off=False,
                last_resume_at=0.0,
            ),
            config=SimpleNamespace(brightness=25, effect="none"),
            _last_brightness=20,
        )

        state = normalize_lighting_power_restore_policy_state(
            tray,
            safe_int_attr_fn=lambda obj, name, default=0: int(getattr(obj, name, default)),
            safe_str_attr_fn=lambda obj, name, default="": str(getattr(obj, name, default)),
            is_software_effect_fn=lambda _effect: False,
            is_reactive_effect_fn=lambda _effect: False,
        )

        assert state.should_restore is False
        assert state.should_log_power_restore is False
        assert tray._idle_forced_off is idle_sentinel
        assert tray._power_forced_off is power_sentinel

    def test_normalize_restore_policy_clears_forced_flags_and_restores_brightness(self):
        from keyrgb.tray._power_restore_policy import normalize_lighting_power_restore_policy_state
        from tests.tray.fakes import make_owner_backed_simple_tray

        tray = make_owner_backed_simple_tray(
            user_forced_off=False,
            idle_forced_off=False,
            power_forced_off=True,
            last_resume_at=0.0,
            last_brightness=40,
            config=SimpleNamespace(brightness=0, effect="reactive_ripple"),
        )

        state = normalize_lighting_power_restore_policy_state(
            tray,
            safe_int_attr_fn=lambda obj, name, default=0: int(getattr(obj, name, default)),
            safe_str_attr_fn=lambda obj, name, default="": str(getattr(obj, name, default)),
            is_software_effect_fn=lambda effect: effect == "rainbow_wave",
            is_reactive_effect_fn=lambda effect: effect.startswith("reactive_"),
        )

        assert state.should_log_power_restore is True
        assert state.should_restore is True
        assert state.is_loop_effect is True
        assert tray._power_forced_off is False
        assert tray.tray_idle_power_state.power_forced_off is False
        assert tray.config.brightness == 40

    def test_power_turn_off_sets_power_forced_flag(self):
        from keyrgb.tray.controllers.lighting_controller import power_turn_off
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=False)

        power_turn_off(mock_tray)

        assert mock_tray._power_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.tray_idle_power_state.power_forced_off is True
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once_with(
            fade=True,
            fade_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_power_restore_restores_when_power_forced(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            user_forced_off=False,
            idle_forced_off=False,
            power_forced_off=True,
            last_brightness=50,
        )
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "breathe"

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        assert mock_tray._power_forced_off is False
        assert mock_tray.tray_idle_power_state.power_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 50
        assert mock_tray.engine.current_color == (0, 0, 0)
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_power_restore_restores_when_off_due_to_hardware_reset(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            power_forced_off=False,
            idle_forced_off=False,
            user_forced_off=False,
        )
        mock_tray.config.brightness = 25
        mock_tray.config.effect = "none"

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        assert mock_tray.is_off is False
        assert mock_tray.engine.current_color == (0, 0, 0)
        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_power_restore_does_not_fight_user_forced_off(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            user_forced_off=True,
            idle_forced_off=False,
            power_forced_off=False,
        )
        mock_tray.config.brightness = 25

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        mock_start.assert_not_called()

    def test_power_restore_user_forced_off_short_circuits_lower_priority_flag_normalization(self):
        from keyrgb.tray.controllers._power._lighting_power_state import power_restore_impl
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        idle_sentinel = object()
        power_sentinel = object()
        tray = SimpleNamespace(
            _user_forced_off=True,
            _idle_forced_off=idle_sentinel,
            _power_forced_off=power_sentinel,
            tray_idle_power_state=TrayIdlePowerState(
                user_forced_off=True,
                idle_forced_off=False,
                power_forced_off=False,
                last_resume_at=0.0,
            ),
            config=SimpleNamespace(brightness=25, effect="none"),
            engine=SimpleNamespace(current_color=(1, 2, 3)),
            is_off=True,
            _last_brightness=20,
            _refresh_ui=MagicMock(),
        )
        start_current_effect = MagicMock()

        with patch("keyrgb.tray.controllers._power._lighting_power_state.time.monotonic", return_value=21.0):
            power_restore_impl(
                tray,
                try_log_event=MagicMock(),
                safe_int_attr_fn=lambda obj, name, default=0: int(getattr(obj, name, default)),
                safe_str_attr_fn=lambda obj, name, default="": str(getattr(obj, name, default)),
                is_software_effect_fn=lambda _effect: False,
                is_reactive_effect_fn=lambda _effect: False,
                start_current_effect=start_current_effect,
            )

        assert tray._idle_forced_off is idle_sentinel
        assert tray._power_forced_off is power_sentinel
        assert tray.tray_idle_power_state.idle_forced_off is False
        assert tray.tray_idle_power_state.power_forced_off is False
        assert tray._last_resume_at == 21.0
        assert tray.tray_idle_power_state.last_resume_at == 21.0
        start_current_effect.assert_not_called()

    def test_power_restore_reads_owner_state_when_legacy_flags_missing(self):
        from keyrgb.tray.controllers._power._lighting_power_state import power_restore_impl
        from tests.tray.fakes import make_owner_backed_simple_tray

        tray = make_owner_backed_simple_tray(
            user_forced_off=True,
            last_resume_at=0.0,
            last_brightness=20,
            config=SimpleNamespace(brightness=25, effect="none"),
            engine=SimpleNamespace(current_color=(1, 2, 3)),
            is_off=True,
            _refresh_ui=MagicMock(),
        )
        # Drop legacy instance attrs so readers must use the typed owner.
        for name in ("_user_forced_off", "_idle_forced_off", "_power_forced_off", "_last_brightness"):
            vars(tray).pop(name, None)

        with patch("keyrgb.tray.controllers._power._lighting_power_state.time.monotonic", return_value=42.0):
            power_restore_impl(
                tray,
                try_log_event=MagicMock(),
                safe_int_attr_fn=lambda obj, name, default=0: int(getattr(obj, name, default)),
                safe_str_attr_fn=lambda obj, name, default="": str(getattr(obj, name, default)),
                is_software_effect_fn=lambda _effect: False,
                is_reactive_effect_fn=lambda _effect: False,
                start_current_effect=MagicMock(),
            )

        assert tray._user_forced_off is True
        assert tray._last_resume_at == 42.0
        assert tray.tray_idle_power_state.last_resume_at == 42.0

    def test_power_restore_falls_back_to_owner_when_legacy_flags_are_invalid(self):
        from keyrgb.tray.controllers._power._lighting_power_state import power_restore_impl
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        start_current_effect = MagicMock()
        tray = SimpleNamespace(
            _user_forced_off=object(),
            _idle_forced_off=object(),
            _power_forced_off=object(),
            tray_idle_power_state=TrayIdlePowerState(
                user_forced_off=False,
                idle_forced_off=False,
                power_forced_off=True,
                last_resume_at=0.0,
            ),
            config=SimpleNamespace(brightness=25, effect="none"),
            engine=SimpleNamespace(current_color=(1, 2, 3)),
            is_off=True,
            _last_brightness=20,
            _refresh_ui=MagicMock(),
        )

        with patch("keyrgb.tray.controllers._power._lighting_power_state.time.monotonic", return_value=9.0):
            power_restore_impl(
                tray,
                try_log_event=MagicMock(),
                safe_int_attr_fn=lambda obj, name, default=0: int(getattr(obj, name, default)),
                safe_str_attr_fn=lambda obj, name, default="": str(getattr(obj, name, default)),
                is_software_effect_fn=lambda _effect: False,
                is_reactive_effect_fn=lambda _effect: False,
                start_current_effect=start_current_effect,
            )

        assert tray._user_forced_off is False
        assert tray._idle_forced_off is False
        assert tray._power_forced_off is False
        assert tray.tray_idle_power_state.power_forced_off is False
        start_current_effect.assert_called_once_with(
            tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_power_restore_loop_effect_uses_soft_on_fade(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            user_forced_off=False,
            idle_forced_off=False,
            power_forced_off=True,
        )
        mock_tray.config.brightness = 25
        mock_tray.config.effect = "reactive_ripple"

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=SOFT_ON_START_BRIGHTNESS,
            fade_in=True,
            fade_in_duration_s=DEFAULT_IDLE_FADE_DURATION_S,
        )

    def test_turn_on_arms_resume_guard(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            user_forced_off=False,
            idle_forced_off=False,
            power_forced_off=False,
            last_brightness=75,
        )
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "breathe"
        mock_tray.tray_idle_power_state.controller_sleep_resume_guard = False

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        mock_start.assert_called_once()
        assert mock_tray.tray_idle_power_state.controller_sleep_resume_guard is True
        # Manual turn-on also clears any prior controller-sleep-off latch.
        assert mock_tray.tray_idle_power_state.controller_sleep_off is False

    def test_power_restore_success_arms_resume_guard(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            user_forced_off=False,
            idle_forced_off=False,
            power_forced_off=True,
            last_brightness=50,
        )
        mock_tray.config.brightness = 0
        mock_tray.config.effect = "breathe"
        mock_tray.tray_idle_power_state.controller_sleep_resume_guard = False

        guard_seen_during_start: list[bool] = []

        def record_guard(*_args, **_kwargs):
            guard_seen_during_start.append(mock_tray.tray_idle_power_state.controller_sleep_resume_guard)

        with patch(
            "keyrgb.tray.controllers.lighting_controller.start_current_effect",
            side_effect=record_guard,
        ) as mock_start:
            power_restore(mock_tray)

        mock_start.assert_called_once()
        assert guard_seen_during_start == [True]
        assert mock_tray.tray_idle_power_state.controller_sleep_resume_guard is True

    def test_power_restore_user_forced_off_does_not_arm_resume_guard(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(
            is_off=True,
            user_forced_off=True,
            idle_forced_off=False,
            power_forced_off=False,
            last_brightness=25,
        )
        mock_tray.config.brightness = 25
        # Pre-arm to prove the non-restore path clears rather than arms.
        mock_tray.tray_idle_power_state.controller_sleep_resume_guard = True

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        mock_start.assert_not_called()
        # User-forced-off is an explicit dark intent: the guard must not stay
        # armed (would otherwise block a later genuine native sleep latch).
        assert mock_tray.tray_idle_power_state.controller_sleep_resume_guard is False


class TestIdleFadeDuration:
    def test_defaults_when_config_lacks_setting(self):
        assert idle_fade_duration_s(SimpleNamespace()) == DEFAULT_IDLE_FADE_DURATION_S

    def test_reads_configured_value(self):
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s=1.2)) == 1.2

    def test_clamps_to_supported_range(self):
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s=0.0)) == 0.1
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s=99.0)) == 3.0

    def test_falls_back_on_uncoercible_value(self):
        assert idle_fade_duration_s(SimpleNamespace(idle_fade_duration_s="fast")) == DEFAULT_IDLE_FADE_DURATION_S

    def test_power_turn_off_uses_configured_fade_duration(self):
        from keyrgb.tray.controllers.lighting_controller import power_turn_off
        from tests.tray.fakes import make_owner_backed_mock_tray

        mock_tray = make_owner_backed_mock_tray(is_off=False)
        mock_tray.config.idle_fade_duration_s = 1.2

        power_turn_off(mock_tray)

        mock_tray.engine.turn_off.assert_called_once_with(fade=True, fade_duration_s=1.2)
