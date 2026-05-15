from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.tray.pollers.time_scheduler import _is_night, _parse_time, _run_scheduler_iteration


class TestParseTime:
    def test_valid_times(self) -> None:
        assert _parse_time("08:00") == (8, 0)
        assert _parse_time("22:30") == (22, 30)
        assert _parse_time("00:00") == (0, 0)
        assert _parse_time("23:59") == (23, 59)

    def test_whitespace_stripped(self) -> None:
        assert _parse_time("  08:00  ") == (8, 0)

    def test_invalid_formats(self) -> None:
        assert _parse_time("08:00:00") is None
        assert _parse_time("0800") is None
        assert _parse_time("") is None
        assert _parse_time("not-a-time") is None

    def test_out_of_range(self) -> None:
        assert _parse_time("24:00") is None
        assert _parse_time("23:60") is None
        assert _parse_time("-1:00") is None


class TestIsNight:
    def test_night_wraps_around_midnight(self) -> None:
        # Night: 20:00 to 08:00
        day_start = (8, 0)
        night_start = (20, 0)

        assert _is_night(datetime(2024, 1, 1, 23, 0), day_start, night_start) is True
        assert _is_night(datetime(2024, 1, 1, 3, 0), day_start, night_start) is True
        assert _is_night(datetime(2024, 1, 1, 8, 0), day_start, night_start) is False
        assert _is_night(datetime(2024, 1, 1, 12, 0), day_start, night_start) is False
        assert _is_night(datetime(2024, 1, 1, 20, 0), day_start, night_start) is True

    def test_night_contiguous_during_day(self) -> None:
        # Night: 02:00 to 14:00
        day_start = (14, 0)
        night_start = (2, 0)

        assert _is_night(datetime(2024, 1, 1, 2, 0), day_start, night_start) is True
        assert _is_night(datetime(2024, 1, 1, 8, 0), day_start, night_start) is True
        assert _is_night(datetime(2024, 1, 1, 13, 59), day_start, night_start) is True
        assert _is_night(datetime(2024, 1, 1, 14, 0), day_start, night_start) is False
        assert _is_night(datetime(2024, 1, 1, 1, 0), day_start, night_start) is False
        assert _is_night(datetime(2024, 1, 1, 15, 0), day_start, night_start) is False

    def test_equal_times_means_always_day(self) -> None:
        day_start = (8, 0)
        night_start = (8, 0)

        assert _is_night(datetime(2024, 1, 1, 0, 0), day_start, night_start) is False
        assert _is_night(datetime(2024, 1, 1, 12, 0), day_start, night_start) is False
        assert _is_night(datetime(2024, 1, 1, 23, 59), day_start, night_start) is False


def test_run_scheduler_iteration_applies_day_reactive_brightness_while_base_is_deferred_to_power_policy() -> None:
    tray = MagicMock()
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._idle_forced_off = False
    tray.config.time_scheduler_enabled = True
    tray.config.day_start_time = "08:00"
    tray.config.night_start_time = "20:00"
    tray.config.day_base_brightness = 25
    tray.config.day_reactive_brightness = 40
    tray.config.night_base_brightness = 10
    tray.config.night_reactive_brightness = 15
    tray.config.power_management_enabled = True
    tray.config.effect = "reactive_ripple"
    tray.config.brightness = 25
    tray.config.perkey_brightness = 25
    tray.config.reactive_brightness = 25
    tray.engine.reactive_brightness = 25

    class _FakeDateTime:
        @staticmethod
        def now() -> datetime:
            return datetime(2024, 1, 1, 12, 0)

    with patch("src.tray.pollers.time_scheduler.datetime", _FakeDateTime):
        _run_scheduler_iteration(tray)

    assert tray.config.brightness == 25
    assert tray.config.perkey_brightness == 25
    assert tray.config.reactive_brightness == 40
    assert tray.engine.reactive_brightness == 40
    tray.engine.set_brightness.assert_not_called()
    tray._refresh_ui.assert_called_once_with()
