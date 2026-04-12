from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.tray.pollers.config_polling_internal import helpers


def _mk_tray() -> SimpleNamespace:
    return SimpleNamespace(
        _log_event=MagicMock(),
        _log_exception=MagicMock(),
        engine=SimpleNamespace(),
    )


def test_log_tray_exception_logs_runtime_logger_failure_and_falls_back() -> None:
    tray = _mk_tray()
    original_exc = RuntimeError("original")
    logger_exc = RuntimeError("logger failed")
    tray._log_exception.side_effect = logger_exc

    with patch.object(helpers, "_log_module_exception") as log_module_exception:
        helpers._log_tray_exception(tray, "Boundary failed: %s", original_exc)

    log_module_exception.assert_any_call("Config polling tray exception logger failed: %s", logger_exc)
    log_module_exception.assert_any_call("Boundary failed: %s", original_exc)


def test_log_tray_exception_propagates_unexpected_logger_failure() -> None:
    tray = _mk_tray()
    tray._log_exception.side_effect = AssertionError("unexpected logger bug")

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        helpers._log_tray_exception(tray, "Boundary failed: %s", RuntimeError("original"))


def test_try_log_event_logs_runtime_failures() -> None:
    tray = _mk_tray()
    event_exc = RuntimeError("event failed")
    tray._log_event.side_effect = event_exc

    with patch.object(helpers, "_log_tray_exception") as log_tray_exception:
        helpers._try_log_event(tray, "config", "change", value=1)

    log_tray_exception.assert_called_once_with(tray, "Config polling event logging failed: %s", event_exc)


def test_try_log_event_propagates_unexpected_failures() -> None:
    tray = _mk_tray()
    tray._log_event.side_effect = AssertionError("unexpected event bug")

    with pytest.raises(AssertionError, match="unexpected event bug"):
        helpers._try_log_event(tray, "config", "change", value=1)


def test_safe_state_for_log_logs_runtime_serialization_failures() -> None:
    tray = _mk_tray()

    def broken_state(_state):
        raise RuntimeError("serialize failed")

    with patch.object(helpers, "_log_tray_exception") as log_tray_exception:
        result = helpers._safe_state_for_log(tray, broken_state, object())

    assert result is None
    log_tray_exception.assert_called_once()
    assert log_tray_exception.call_args.args[0] is tray
    assert log_tray_exception.call_args.args[1] == "Failed to serialize config polling state for logs: %s"
    assert str(log_tray_exception.call_args.args[2]) == "serialize failed"


def test_safe_state_for_log_propagates_unexpected_failures() -> None:
    tray = _mk_tray()

    def broken_state(_state):
        raise AssertionError("unexpected serializer bug")

    with pytest.raises(AssertionError, match="unexpected serializer bug"):
        helpers._safe_state_for_log(tray, broken_state, object())


def test_call_tray_callback_logs_runtime_failures() -> None:
    tray = _mk_tray()
    callback_exc = RuntimeError("callback failed")
    tray._refresh_ui = MagicMock(side_effect=callback_exc)

    with patch.object(helpers, "_log_tray_exception") as log_tray_exception:
        helpers._call_tray_callback(tray, "_refresh_ui", error_msg="Refresh failed: %s")

    log_tray_exception.assert_called_once_with(tray, "Refresh failed: %s", callback_exc)


def test_call_tray_callback_propagates_unexpected_failures() -> None:
    tray = _mk_tray()
    tray._refresh_ui = MagicMock(side_effect=AssertionError("unexpected callback bug"))

    with pytest.raises(AssertionError, match="unexpected callback bug"):
        helpers._call_tray_callback(tray, "_refresh_ui", error_msg="Refresh failed: %s")


def test_set_engine_attr_best_effort_logs_runtime_setter_failures() -> None:
    tray = _mk_tray()

    class BrokenEngine:
        @property
        def reactive_color(self):
            return None

        @reactive_color.setter
        def reactive_color(self, _value):
            raise RuntimeError("setter failed")

    tray.engine = BrokenEngine()

    with patch.object(helpers, "_log_tray_exception") as log_tray_exception:
        helpers._set_engine_attr_best_effort(
            tray,
            "reactive_color",
            (1, 2, 3),
            error_msg="Setter failed: %s",
        )

    log_tray_exception.assert_called_once()
    assert log_tray_exception.call_args.args[0] is tray
    assert log_tray_exception.call_args.args[1] == "Setter failed: %s"
    assert str(log_tray_exception.call_args.args[2]) == "setter failed"


def test_set_engine_attr_best_effort_propagates_unexpected_setter_failures() -> None:
    tray = _mk_tray()

    class BrokenEngine:
        @property
        def reactive_color(self):
            return None

        @reactive_color.setter
        def reactive_color(self, _value):
            raise AssertionError("unexpected setter bug")

    tray.engine = BrokenEngine()

    with pytest.raises(AssertionError, match="unexpected setter bug"):
        helpers._set_engine_attr_best_effort(
            tray,
            "reactive_color",
            (1, 2, 3),
            error_msg="Setter failed: %s",
        )


def test_enable_user_mode_best_effort_logs_runtime_fallback_failures() -> None:
    tray = _mk_tray()
    tray.engine = SimpleNamespace(kb=SimpleNamespace())

    def enable_user_mode(*, brightness: int, save: bool = False):
        if save:
            raise TypeError("save not supported")
        raise RuntimeError("fallback failed")

    tray.engine.kb.enable_user_mode = enable_user_mode

    with patch.object(helpers, "_log_tray_exception") as log_tray_exception:
        helpers._enable_user_mode_best_effort(tray, brightness=10)

    log_tray_exception.assert_called_once()
    assert log_tray_exception.call_args.args[0] is tray
    assert log_tray_exception.call_args.args[1] == "Failed to enable per-key user mode fallback: %s"
    assert str(log_tray_exception.call_args.args[2]) == "fallback failed"


def test_enable_user_mode_best_effort_propagates_unexpected_fallback_failures() -> None:
    tray = _mk_tray()
    tray.engine = SimpleNamespace(kb=SimpleNamespace())

    def enable_user_mode(*, brightness: int, save: bool = False):
        if save:
            raise TypeError("save not supported")
        raise AssertionError("unexpected fallback bug")

    tray.engine.kb.enable_user_mode = enable_user_mode

    with pytest.raises(AssertionError, match="unexpected fallback bug"):
        helpers._enable_user_mode_best_effort(tray, brightness=10)