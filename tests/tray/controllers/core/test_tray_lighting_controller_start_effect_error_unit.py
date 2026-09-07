from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestStartCurrentEffectErrors:
    def test_start_current_effect_handles_exception_gracefully(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=RuntimeError("hardware error"))

        result = start_current_effect(mock_tray)

        assert result is False
        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args.args[0] == "Error starting effect: %s"
        assert str(mock_tray._log_exception.call_args.args[1]) == "hardware error"

    def test_start_current_effect_reports_success(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "breathe"
        mock_tray.config.brightness = 40
        mock_tray.config.get_effect_speed.return_value = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        assert start_current_effect(mock_tray) is True

    def test_start_current_effect_propagates_unexpected_startup_errors(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=AssertionError("unexpected startup bug"))

        with pytest.raises(AssertionError, match="unexpected startup bug"):
            start_current_effect(mock_tray)

    def test_start_current_effect_logs_ensure_device_failures(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine._ensure_device_available = MagicMock(side_effect=RuntimeError("probe failed"))

        start_current_effect(mock_tray)

        mock_tray.engine.start_effect.assert_not_called()
        mock_tray._log_exception.assert_called_once()
        assert mock_tray._log_exception.call_args.args[0] == "Error starting effect: %s"
        assert isinstance(mock_tray._log_exception.call_args.args[1], RuntimeError)

    def test_start_current_effect_falls_back_to_logger_when_tray_logging_raises(self):
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        original_exc = RuntimeError("hardware error")
        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=original_exc)
        mock_tray._log_exception = MagicMock(side_effect=RuntimeError("logger failed"))

        with (
            patch("keyrgb.tray.controllers.lighting_controller.logger.exception") as log_exception,
            patch("keyrgb.tray.controllers.lighting_controller.logger.error") as log_error,
        ):
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
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

        original_exc = RuntimeError("hardware error")
        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=original_exc)
        mock_tray._log_exception = MagicMock(side_effect=AssertionError("unexpected logger bug"))

        with pytest.raises(AssertionError, match="unexpected logger bug"):
            start_current_effect(mock_tray)

    def test_log_boundary_exception_propagates_unexpected_logger_errors(self):
        from keyrgb.tray.controllers.lighting_controller import _log_boundary_exception

        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=AssertionError("unexpected logger bug"))

        with pytest.raises(AssertionError, match="unexpected logger bug"):
            _log_boundary_exception(tray, "Failed to mark device unavailable: %s", RuntimeError("boom"))

    def test_start_current_effect_runtime_exception_tuple_is_runtime_category(self):
        from keyrgb.tray.controllers.lighting_controller import _START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS

        assert _START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS == (
            AttributeError,
            LookupError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        )

    def test_tray_logger_callback_exception_tuple_is_runtime_category(self):
        from keyrgb.tray.controllers.lighting_controller import _TRAY_LOGGER_CALLBACK_EXCEPTIONS

        assert _TRAY_LOGGER_CALLBACK_EXCEPTIONS == (
            AttributeError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        )

    def test_log_boundary_exception_falls_back_to_module_logger_with_traceback(self):
        from keyrgb.tray.controllers.lighting_controller import _log_boundary_exception

        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=RuntimeError("logger failed"))
        original_exc = None

        try:
            raise RuntimeError("hardware error")
        except RuntimeError as raised_exc:
            original_exc = raised_exc
            with (
                patch("keyrgb.tray.controllers.lighting_controller.logger.exception") as log_exception,
                patch("keyrgb.tray.controllers.lighting_controller.logger.error") as log_error,
            ):
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
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

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
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

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
        from keyrgb.tray.controllers.lighting_controller import start_current_effect

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
        mock_tray.config.reactive_visual_mode = "subtle"

        start_current_effect(mock_tray)

        assert mock_tray.config.effect == "rainbow_wave"
        mock_tray.engine.start_effect.assert_called_once_with(
            "rainbow_wave",
            speed=3,
            brightness=40,
            color=(1, 2, 3),
            reactive_color=None,
            reactive_use_manual_color=False,
            reactive_visual_mode="subtle",
            direction=mock_tray.config.direction,
        )
