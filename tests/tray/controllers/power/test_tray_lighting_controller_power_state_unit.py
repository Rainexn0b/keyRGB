from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.tray.controllers._power._transition_constants import (
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
    def test_normalize_restore_policy_short_circuits_on_user_forced_off(self):
        from src.tray.protocols import TrayIdlePowerState, normalize_lighting_power_restore_policy_state

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
        from src.tray.protocols import TrayIdlePowerState, normalize_lighting_power_restore_policy_state

        tray = SimpleNamespace(
            _user_forced_off=False,
            _idle_forced_off=False,
            _power_forced_off=True,
            tray_idle_power_state=TrayIdlePowerState(
                user_forced_off=False,
                idle_forced_off=False,
                power_forced_off=True,
                last_resume_at=0.0,
            ),
            config=SimpleNamespace(brightness=0, effect="reactive_ripple"),
            _last_brightness=40,
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

    def test_power_restore_user_forced_off_short_circuits_lower_priority_flag_normalization(self):
        from src.tray.controllers._power._lighting_power_state import power_restore_impl
        from src.tray.protocols import TrayIdlePowerState

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

        with patch("src.tray.controllers._power._lighting_power_state.time.monotonic", return_value=21.0):
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
        from src.tray.controllers._power._lighting_power_state import power_restore_impl
        from src.tray.protocols import TrayIdlePowerState

        tray = SimpleNamespace(
            tray_idle_power_state=TrayIdlePowerState(user_forced_off=True, last_resume_at=0.0),
            config=SimpleNamespace(brightness=25, effect="none"),
            engine=SimpleNamespace(current_color=(1, 2, 3)),
            is_off=True,
            _last_brightness=20,
            _refresh_ui=MagicMock(),
        )

        with patch("src.tray.controllers._power._lighting_power_state.time.monotonic", return_value=42.0):
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
        from src.tray.controllers._power._lighting_power_state import power_restore_impl
        from src.tray.protocols import TrayIdlePowerState

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

        with patch("src.tray.controllers._power._lighting_power_state.time.monotonic", return_value=9.0):
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
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )

    def test_power_restore_loop_effect_uses_in_place_restart(self):
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._user_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = True
        mock_tray.is_off = True
        mock_tray.config.brightness = 25
        mock_tray.config.effect = "reactive_ripple"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        mock_start.assert_called_once_with(
            mock_tray,
            brightness_override=None,
            fade_in=False,
            fade_in_duration_s=SOFT_ON_FADE_DURATION_S,
        )
