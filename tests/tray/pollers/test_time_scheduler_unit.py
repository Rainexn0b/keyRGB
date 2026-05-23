from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.tray.pollers.time_scheduler import _active_power_source_base_brightness, _is_night, _parse_time
from src.tray.pollers.time_scheduler import _run_scheduler_iteration, _scheduler_loop


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


def test_run_scheduler_iteration_applies_day_base_brightness_when_power_policy_has_no_base_override() -> None:
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
    tray.engine.set_brightness.assert_called_once_with(
        25,
        apply_to_hardware=False,
        fade=False,
        fade_duration_s=0.25,
    )
    assert tray.config.reactive_brightness == 40
    assert tray.engine.reactive_brightness == 40
    tray._refresh_ui.assert_called_once_with()


def test_run_scheduler_iteration_uses_ac_brightness_as_day_primary_when_configured() -> None:
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
    tray.config.ac_lighting_brightness = 35
    tray.config.battery_lighting_brightness = 20
    tray.config.effect = "reactive_ripple"
    tray.config.brightness = 25
    tray.config.perkey_brightness = 25
    tray.config.reactive_brightness = 25
    tray.engine.reactive_brightness = 25

    class _FakeDateTime:
        @staticmethod
        def now() -> datetime:
            return datetime(2024, 1, 1, 12, 0)

    with (
        patch("src.tray.pollers.time_scheduler.datetime", _FakeDateTime),
        patch("src.tray.pollers.time_scheduler.read_on_ac_power", return_value=True),
    ):
        _run_scheduler_iteration(tray)

    assert tray.config.brightness == 35
    assert tray.config.perkey_brightness == 35
    assert tray.config.reactive_brightness == 40
    assert tray.engine.reactive_brightness == 40
    tray.engine.set_brightness.assert_called_once_with(
        35,
        apply_to_hardware=False,
        fade=False,
        fade_duration_s=0.25,
    )
    tray._refresh_ui.assert_called_once_with()


def test_run_scheduler_iteration_applies_day_base_when_only_inactive_power_source_override_exists() -> None:
    tray = MagicMock()
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._idle_forced_off = False
    tray.config.time_scheduler_enabled = True
    tray.config.day_start_time = "08:00"
    tray.config.night_start_time = "20:00"
    tray.config.day_base_brightness = 30
    tray.config.day_reactive_brightness = 45
    tray.config.night_base_brightness = 10
    tray.config.night_reactive_brightness = 15
    tray.config.power_management_enabled = True
    tray.config.ac_lighting_brightness = None
    tray.config.battery_lighting_brightness = 20
    tray.config.effect = "reactive_ripple"
    tray.config.brightness = 80
    tray.config.perkey_brightness = 80
    tray.config.reactive_brightness = 25
    tray.engine.reactive_brightness = 25

    class _FakeDateTime:
        @staticmethod
        def now() -> datetime:
            return datetime(2024, 1, 1, 12, 0)

    with (
        patch("src.tray.pollers.time_scheduler.datetime", _FakeDateTime),
        patch("src.tray.pollers.time_scheduler.read_on_ac_power", return_value=True),
    ):
        _run_scheduler_iteration(tray)

    assert tray.config.brightness == 30
    assert tray.config.perkey_brightness == 30
    tray.engine.set_brightness.assert_called_once_with(
        30,
        apply_to_hardware=False,
        fade=True,
        fade_duration_s=0.25,
    )


def test_active_power_source_base_brightness_uses_day_policy() -> None:
    config = MagicMock()
    config.time_scheduler_enabled = True
    config.day_start_time = "08:00"
    config.night_start_time = "20:00"
    config.day_base_brightness = 30
    config.day_reactive_brightness = 50
    config.night_base_brightness = 20
    config.night_reactive_brightness = 25
    config.ac_lighting_brightness = 40
    config.battery_lighting_brightness = 20

    from src.core.brightness_layers import resolve_scheduler_brightness_state

    state = resolve_scheduler_brightness_state(
        config,
        now=datetime(2024, 1, 1, 11, 10),
        power_management_enabled=True,
    )

    assert _active_power_source_base_brightness(state, on_ac=None) is None
    assert _active_power_source_base_brightness(state, on_ac=True) == 40
    assert _active_power_source_base_brightness(state, on_ac=False) == 20


def test_active_power_source_base_brightness_uses_lower_value_at_night() -> None:
    config = MagicMock()
    config.time_scheduler_enabled = True
    config.day_start_time = "08:00"
    config.night_start_time = "20:00"
    config.day_base_brightness = 30
    config.day_reactive_brightness = 50
    config.night_base_brightness = 20
    config.night_reactive_brightness = 25
    config.ac_lighting_brightness = 40
    config.battery_lighting_brightness = 15

    from src.core.brightness_layers import resolve_scheduler_brightness_state

    state = resolve_scheduler_brightness_state(
        config,
        now=datetime(2024, 1, 1, 22, 10),
        power_management_enabled=True,
    )

    assert _active_power_source_base_brightness(state, on_ac=None) is None
    assert _active_power_source_base_brightness(state, on_ac=True) == 20
    assert _active_power_source_base_brightness(state, on_ac=False) == 15


def test_scheduler_loop_retries_same_key_after_power_forced_off_skip() -> None:
    tray = MagicMock()
    tray._user_forced_off = False
    tray._power_forced_off = True
    tray._idle_forced_off = False
    tray.is_off = False
    tray.config.time_scheduler_enabled = True
    tray.config.day_start_time = "08:00"
    tray.config.night_start_time = "20:00"
    tray.config.day_base_brightness = 40
    tray.config.day_reactive_brightness = 50
    tray.config.night_base_brightness = 20
    tray.config.night_reactive_brightness = 45
    tray.config.power_management_enabled = True
    tray.config.ac_lighting_brightness = 40
    tray.config.battery_lighting_brightness = 20
    tray.config.effect = "reactive_ripple"
    tray.config.brightness = 40
    tray.config.perkey_brightness = 40
    tray.config.reactive_brightness = 50
    tray.engine.reactive_brightness = 50

    class StopLoop(Exception):
        pass

    sleep_calls = 0

    def sleep_fn(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 1:
            tray._power_forced_off = False
            return
        raise StopLoop

    with (
        patch("src.tray.pollers.time_scheduler.read_on_ac_power", return_value=True),
        pytest.raises(StopLoop),
    ):
        _scheduler_loop(
            tray,
            sleep_fn=sleep_fn,
            now_fn=lambda: datetime(2024, 1, 1, 22, 0),
        )

    tray.engine.set_brightness.assert_called_once_with(
        20,
        apply_to_hardware=False,
        fade=True,
        fade_duration_s=0.25,
    )
    assert tray.config.brightness == 20
    assert tray.config.reactive_brightness == 45
