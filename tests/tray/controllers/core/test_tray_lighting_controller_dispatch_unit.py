from __future__ import annotations

import logging
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.core.effects.reactive import _render_brightness_support as reactive_support


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestParseMenuInt:
    def test_parse_menu_int_strips_radio_markers(self):
        from src.tray.controllers._lighting_controller_helpers import parse_menu_int

        assert parse_menu_int("🔘 50") == 50
        assert parse_menu_int("⚪ 75") == 75
        assert parse_menu_int("100") == 100

    def test_parse_menu_int_returns_none_on_invalid(self):
        from src.tray.controllers._lighting_controller_helpers import parse_menu_int

        assert parse_menu_int("not a number") is None
        assert parse_menu_int("🔘 abc") is None

    def test_parse_menu_int_logs_when_stringification_raises(self, caplog):
        from src.tray.controllers._lighting_controller_helpers import parse_menu_int

        class BadMenuItem:
            def __str__(self) -> str:
                raise RuntimeError("bad menu item")

        with caplog.at_level(logging.ERROR):
            assert parse_menu_int(BadMenuItem()) is None

        records = [r for r in caplog.records if "Failed parsing tray menu integer item" in r.message]
        assert records
        assert records[0].exc_info is not None

    def test_parse_menu_int_propagates_unexpected_stringification_errors(self):
        from src.tray.controllers._lighting_controller_helpers import parse_menu_int

        class BadMenuItem:
            def __str__(self) -> str:
                raise AssertionError("unexpected menu item bug")

        with pytest.raises(AssertionError, match="unexpected menu item bug"):
            parse_menu_int(BadMenuItem())


class TestHelperBoundaries:
    def test_config_per_key_colors_logs_recoverable_getter_failure(self, caplog):
        from src.tray.controllers._lighting_controller_helpers import _config_per_key_colors_ref

        class BadConfig:
            @property
            def per_key_colors(self):
                raise RuntimeError("bad config")

        with caplog.at_level(logging.ERROR):
            assert _config_per_key_colors_ref(BadConfig()) is None

        records = [r for r in caplog.records if "Failed reading config per-key colors" in r.message]
        assert records
        assert records[0].exc_info is not None

    def test_set_engine_attr_best_effort_logs_recoverable_runtime_error(self):
        from src.tray.controllers._lighting_controller_helpers import _set_engine_attr_best_effort

        class RejectingEngine:
            def __init__(self):
                self._per_key_colors = {(9, 9): (9, 9, 9)}

            @property
            def per_key_colors(self):
                return self._per_key_colors

            @per_key_colors.setter
            def per_key_colors(self, value):
                if value is not None:
                    raise RuntimeError("cannot set colors")
                self._per_key_colors = value

        tray = MagicMock()
        tray.engine = RejectingEngine()

        _set_engine_attr_best_effort(
            tray,
            "per_key_colors",
            {(0, 0): (255, 0, 0)},
            error_msg="Failed to apply per-key colors to engine: %s",
            fallback=None,
        )

        tray._log_exception.assert_called_once()
        assert tray._log_exception.call_args.args[0] == "Failed to apply per-key colors to engine: %s"
        assert str(tray._log_exception.call_args.args[1]) == "cannot set colors"
        assert tray.engine.per_key_colors is None

    def test_log_tray_exception_falls_back_to_module_logger_when_tray_logger_raises(self):
        from src.tray.controllers import _lighting_controller_helpers as helpers

        original_exc = RuntimeError("hardware error")
        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=RuntimeError("logger failed"))

        with patch.object(helpers.logger, "exception") as log_exception:
            with patch.object(helpers.logger, "error") as log_error:
                helpers._log_tray_exception(tray, "Helper error: %s", original_exc)

        tray._log_exception.assert_called_once_with("Helper error: %s", original_exc)
        log_exception.assert_called_once()
        assert log_exception.call_args.args[0] == "Tray exception logger failed while logging boundary: %s"
        assert str(log_exception.call_args.args[1]) == "logger failed"

        log_error.assert_called_once_with(
            "Helper error: %s",
            original_exc,
            exc_info=(RuntimeError, original_exc, original_exc.__traceback__),
        )

    def test_log_tray_exception_propagates_unexpected_logger_failures(self):
        from src.tray.controllers import _lighting_controller_helpers as helpers

        original_exc = RuntimeError("hardware error")
        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=AssertionError("unexpected logger bug"))

        with pytest.raises(AssertionError, match="unexpected logger bug"):
            helpers._log_tray_exception(tray, "Helper error: %s", original_exc)

    def test_try_log_event_logs_recoverable_runtime_errors(self):
        from src.tray.controllers._lighting_controller_helpers import try_log_event

        tray = MagicMock()
        tray._log_event = MagicMock(side_effect=RuntimeError("event logger failed"))

        with patch("src.tray.controllers._lighting_controller_helpers.logger.error") as log_error:
            try_log_event(tray, "tray", "clicked", effect="wave")

        tray._log_event.assert_called_once_with("tray", "clicked", effect="wave")
        log_error.assert_called_once()
        assert log_error.call_args.args[0] == "Tray event logging failed: %s"
        assert str(log_error.call_args.args[1]) == "event logger failed"

    def test_try_log_event_propagates_unexpected_logger_errors(self):
        from src.tray.controllers._lighting_controller_helpers import try_log_event

        tray = MagicMock()
        tray._log_event = MagicMock(side_effect=AssertionError("unexpected event logger bug"))

        with pytest.raises(AssertionError, match="unexpected event logger bug"):
            try_log_event(tray, "tray", "clicked", effect="wave")


class TestStartCurrentEffect:
    def test_resolve_start_current_effect_policy_keeps_config_unchanged(self):
        from src.tray.controllers.lighting_controller import _resolve_start_current_effect_policy

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

    def test_resolve_start_current_effect_policy_reports_canonical_effect_persist(self):
        from src.tray.controllers.lighting_controller import _resolve_start_current_effect_policy

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
        from src.tray.controllers.lighting_controller import _classify_start_current_effect

        tray = MagicMock()
        plan = _classify_start_current_effect(tray, effect="perkey")

        assert plan.is_perkey_mode is True
        assert plan.is_none_mode is False
        assert plan.is_loop_effect is False

    def test_classify_start_current_effect_marks_loop_effect(self):
        from src.tray.controllers.lighting_controller import _classify_start_current_effect

        tray = MagicMock()
        plan = _classify_start_current_effect(tray, effect="rainbow_wave")

        assert plan.is_perkey_mode is False
        assert plan.is_none_mode is False
        assert plan.is_loop_effect is True

    def test_plan_effect_fade_ramp_marks_loop_effect_as_non_hardware(self):
        from src.tray.controllers.lighting_controller import _plan_effect_fade_ramp

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
        from src.tray.controllers.lighting_controller import _plan_effect_fade_ramp

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
        from src.tray.controllers import _lighting_effect_coordination

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
        from src.tray.controllers import _lighting_effect_coordination

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

    def test_start_current_effect_fade_for_loop_effect_uses_non_hardware_brightness_write(self):
        from src.tray.controllers.lighting_controller import start_current_effect

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

    def test_start_current_effect_idle_restore_loop_effect_uses_legacy_non_hardware_fade_without_follow_global(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray._idle_restore_legacy_loop_effect_ramp = True
        mock_tray.config.effect = "rainbow_wave"
        mock_tray.config.brightness = 50
        mock_tray.config.perkey_brightness = 50
        mock_tray.config.per_key_colors = {}
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False
        reactive_support.ensure_reactive_state(mock_tray.engine)._reactive_follow_global_brightness = False
        mock_tray.engine.reactive_brightness = 50
        mock_tray.engine.per_key_brightness = 50

        start_current_effect(mock_tray, brightness_override=10, fade_in=True, fade_in_duration_s=0.42)

        mock_tray.engine.start_effect.assert_called_once_with(
            "rainbow_wave",
            speed=3,
            brightness=10,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
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

    def test_start_current_effect_fade_for_hardware_effect_uses_hardware_fade(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "breathe"
        mock_tray.config.brightness = 50
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        start_current_effect(mock_tray, brightness_override=10, fade_in=True, fade_in_duration_s=0.42)

        mock_tray.engine.start_effect.assert_called_once_with(
            "breathe",
            speed=3,
            brightness=10,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
            direction=mock_tray.config.direction,
        )
        mock_tray.engine.set_brightness.assert_called_once_with(
            50,
            apply_to_hardware=True,
            fade=True,
            fade_duration_s=0.42,
        )

    def test_perkey_effect_calls_set_key_colors(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 50
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.enable_user_mode = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = _lock_mock()

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_key_colors.assert_called_once()
        assert mock_tray.is_off is False

    def test_perkey_turns_off_if_brightness_zero(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 0

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.turn_off.assert_called_once()
        assert mock_tray.is_off is True

    def test_none_effect_calls_set_color(self):
        from src.tray.controllers.lighting_controller import start_current_effect

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
        from src.tray.controllers.lighting_controller import start_current_effect

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

        with patch("src.tray.controllers.lighting_controller.restore_secondary_software_targets") as restore:
            start_current_effect(mock_tray)

        mock_tray.engine.kb.set_color.assert_called_once_with((255, 0, 0), brightness=75)
        restore.assert_called_once_with(mock_tray)

    def test_animated_effect_starts_engine(self):
        from src.tray.controllers.lighting_controller import start_current_effect

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
            direction=mock_tray.config.direction,
        )
        assert mock_tray.is_off is False

    def test_start_current_effect_handles_exception_gracefully(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=RuntimeError("hardware error"))

        start_current_effect(mock_tray)

        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args.args[0] == "Error starting effect: %s"
        assert str(mock_tray._log_exception.call_args.args[1]) == "hardware error"

    def test_start_current_effect_propagates_unexpected_startup_errors(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=AssertionError("unexpected startup bug"))

        with pytest.raises(AssertionError, match="unexpected startup bug"):
            start_current_effect(mock_tray)

    def test_start_current_effect_logs_ensure_device_failures(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine._ensure_device_available = MagicMock(side_effect=RuntimeError("probe failed"))

        start_current_effect(mock_tray)

        mock_tray.engine.start_effect.assert_not_called()
        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args.args[0] == "Error starting effect: %s"
        assert isinstance(mock_tray._log_exception.call_args.args[1], RuntimeError)

    def test_start_current_effect_falls_back_to_logger_when_tray_logging_raises(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        original_exc = RuntimeError("hardware error")
        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=original_exc)
        mock_tray._log_exception = MagicMock(side_effect=RuntimeError("logger failed"))

        with patch("src.tray.controllers.lighting_controller.logger.exception") as log_exception:
            with patch("src.tray.controllers.lighting_controller.logger.error") as log_error:
                start_current_effect(mock_tray)

        mock_tray._log_exception.assert_called_once_with("Error starting effect: %s", original_exc)
        log_exception.assert_called_once()
        assert log_exception.call_args.args[0] == "Tray exception logger failed while logging boundary: %s"
        assert str(log_exception.call_args.args[1]) == "logger failed"

        log_error.assert_called_once()
        assert log_error.call_args.args[0] == "Error starting effect: %s"
        assert log_error.call_args.args[1] is original_exc
        exc_info = log_error.call_args.kwargs["exc_info"]
        assert exc_info[0] is RuntimeError
        assert exc_info[1] is original_exc
        assert exc_info[2] is original_exc.__traceback__
        assert exc_info[2] is not None

    def test_start_current_effect_propagates_unexpected_tray_logging_errors(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        original_exc = RuntimeError("hardware error")
        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=original_exc)
        mock_tray._log_exception = MagicMock(side_effect=AssertionError("unexpected logger bug"))

        with pytest.raises(AssertionError, match="unexpected logger bug"):
            start_current_effect(mock_tray)

    def test_log_boundary_exception_propagates_unexpected_logger_errors(self):
        from src.tray.controllers.lighting_controller import _log_boundary_exception

        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=AssertionError("unexpected logger bug"))

        with pytest.raises(AssertionError, match="unexpected logger bug"):
            _log_boundary_exception(tray, "Failed to mark device unavailable: %s", RuntimeError("boom"))

    def test_start_current_effect_runtime_exception_tuple_is_runtime_category(self):
        from src.tray.controllers.lighting_controller import _START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS

        assert _START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS == (
            AttributeError,
            LookupError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        )

    def test_tray_logger_callback_exception_tuple_is_runtime_category(self):
        from src.tray.controllers.lighting_controller import _TRAY_LOGGER_CALLBACK_EXCEPTIONS

        assert _TRAY_LOGGER_CALLBACK_EXCEPTIONS == (
            AttributeError,
            LookupError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        )

    def test_log_boundary_exception_falls_back_to_module_logger_with_traceback(self):
        from src.tray.controllers.lighting_controller import _log_boundary_exception

        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=RuntimeError("logger failed"))
        original_exc = None

        try:
            raise RuntimeError("hardware error")
        except RuntimeError as raised_exc:
            original_exc = raised_exc
            with patch("src.tray.controllers.lighting_controller.logger.exception") as log_exception:
                with patch("src.tray.controllers.lighting_controller.logger.error") as log_error:
                    _log_boundary_exception(tray, "Error starting effect: %s", original_exc)

        assert original_exc is not None
        tray._log_exception.assert_called_once_with("Error starting effect: %s", original_exc)
        log_exception.assert_called_once_with(
            "Tray exception logger failed while logging boundary: %s",
            tray._log_exception.side_effect,
        )
        log_error.assert_called_once_with(
            "Error starting effect: %s",
            original_exc,
            exc_info=(RuntimeError, original_exc, original_exc.__traceback__),
        )
        assert original_exc.__traceback__ is not None

    def test_start_current_effect_logs_mark_unavailable_failure_on_disconnect(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        class DisconnectError(OSError):
            def __init__(self):
                super().__init__("No such device")
                self.errno = 19

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=DisconnectError())
        mock_tray.engine.mark_device_unavailable = MagicMock(side_effect=RuntimeError("mark failed"))

        start_current_effect(mock_tray)

        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args[0][0] == "Failed to mark device unavailable: %s"
        assert str(mock_tray._log_exception.call_args[0][1]) == "mark failed"

    def test_start_current_effect_logs_notification_failure_for_permission_errors(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=PermissionError("denied"))
        mock_tray._notify_permission_issue = MagicMock(side_effect=RuntimeError("notify failed"))

        start_current_effect(mock_tray)

        mock_tray._notify_permission_issue.assert_called_once()
        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args[0][0] == "Failed to notify permission issue: %s"
        assert str(mock_tray._log_exception.call_args[0][1]) == "notify failed"

    def test_start_current_effect_resolves_prefixed_hardware_name_before_engine_start(self):
        from src.tray.controllers.lighting_controller import start_current_effect

        backend = MagicMock()
        backend.effects.return_value = {"rainbow_wave": object()}

        mock_tray = MagicMock()
        mock_tray.backend = backend
        mock_tray.config.effect = "hw:rainbow_wave"
        mock_tray.config.brightness = 40
        mock_tray.config.speed = 3
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (1, 2, 3)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        start_current_effect(mock_tray)

        assert mock_tray.config.effect == "rainbow_wave"
        mock_tray.engine.start_effect.assert_called_once_with(
            "rainbow_wave",
            speed=3,
            brightness=40,
            color=(1, 2, 3),
            reactive_color=None,
            reactive_use_manual_color=False,
            direction=mock_tray.config.direction,
        )
