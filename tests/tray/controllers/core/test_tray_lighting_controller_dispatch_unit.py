from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


def _lock_mock() -> MagicMock:
    return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)


class TestParseMenuInt:
    def test_parse_menu_int_strips_radio_markers(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import parse_menu_int

        assert parse_menu_int("🔘 50") == 50
        assert parse_menu_int("⚪ 75") == 75
        assert parse_menu_int("100") == 100

    def test_parse_menu_int_returns_none_on_invalid(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import parse_menu_int

        assert parse_menu_int("not a number") is None
        assert parse_menu_int("🔘 abc") is None

    def test_parse_menu_int_logs_when_stringification_raises(self, caplog):
        from keyrgb.tray.controllers._lighting_controller_helpers import parse_menu_int

        class BadMenuItem:
            def __str__(self) -> str:
                raise RuntimeError("bad menu item")

        with caplog.at_level(logging.ERROR):
            assert parse_menu_int(BadMenuItem()) is None

        records = [r for r in caplog.records if "Failed parsing tray menu integer item" in r.message]
        assert records
        assert records[0].exc_info is not None

    def test_parse_menu_int_propagates_unexpected_stringification_errors(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import parse_menu_int

        class BadMenuItem:
            def __str__(self) -> str:
                raise AssertionError("unexpected menu item bug")

        with pytest.raises(AssertionError, match="unexpected menu item bug"):
            parse_menu_int(BadMenuItem())


class TestHelperBoundaries:
    def test_config_per_key_colors_logs_recoverable_getter_failure(self, caplog):
        from keyrgb.tray.controllers._lighting_controller_helpers import _config_per_key_colors_ref

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
        from keyrgb.tray.controllers._lighting_controller_helpers import _set_engine_attr_best_effort

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
        from keyrgb.tray.controllers import _lighting_controller_helpers as helpers

        original_exc = RuntimeError("hardware error")
        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=RuntimeError("logger failed"))

        with (
            patch.object(helpers.logger, "exception") as log_exception,
            patch.object(helpers.logger, "error") as log_error,
        ):
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
        from keyrgb.tray.controllers import _lighting_controller_helpers as helpers

        original_exc = RuntimeError("hardware error")
        tray = MagicMock()
        tray._log_exception = MagicMock(side_effect=AssertionError("unexpected logger bug"))

        with pytest.raises(AssertionError, match="unexpected logger bug"):
            helpers._log_tray_exception(tray, "Helper error: %s", original_exc)

    def test_try_log_event_logs_recoverable_runtime_errors(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import try_log_event

        tray = MagicMock()
        tray._log_event = MagicMock(side_effect=RuntimeError("event logger failed"))

        with patch("keyrgb.tray.controllers._lighting_controller_helpers.logger.error") as log_error:
            try_log_event(tray, "tray", "clicked", effect="wave")

        tray._log_event.assert_called_once_with("tray", "clicked", effect="wave")
        log_error.assert_called_once()
        assert log_error.call_args.args[0] == "Tray event logging failed: %s"
        assert str(log_error.call_args.args[1]) == "event logger failed"

    def test_try_log_event_propagates_unexpected_logger_errors(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import try_log_event

        tray = MagicMock()
        tray._log_event = MagicMock(side_effect=AssertionError("unexpected event logger bug"))

        with pytest.raises(AssertionError, match="unexpected event logger bug"):
            try_log_event(tray, "tray", "clicked", effect="wave")

    def test_get_effect_name_prefers_live_engine_effect_over_config_snapshot(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import get_effect_name

        tray = MagicMock()
        tray.engine.current_effect = "reactive_ripple"
        tray.config.effect = "perkey"

        assert get_effect_name(tray) == "reactive_ripple"

    def test_get_effect_name_promotes_base_only_state_when_engine_effect_is_unset(self):
        from keyrgb.tray.controllers._lighting_controller_helpers import get_effect_name

        tray = MagicMock()
        tray.engine.current_effect = None
        tray.config.effect = "none"
        tray.config.per_key_colors = {(0, 0): (255, 0, 0)}

        assert get_effect_name(tray) == "perkey"
