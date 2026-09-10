from __future__ import annotations

from datetime import datetime as _datetime, timezone
from types import SimpleNamespace

import pytest

from keyrgb.core.power.system import PowerMode
from keyrgb.gui.settings import settings_state
from keyrgb.gui.settings.settings_state import (
    SettingsValues,
    apply_settings_values_to_config,
)


def _settings_values(**overrides) -> SettingsValues:
    values = {
        "power_management_enabled": True,
        "power_off_on_suspend": True,
        "power_off_on_lid_close": True,
        "power_restore_on_resume": True,
        "power_restore_on_lid_open": True,
        "autostart": True,
        "experimental_backends_enabled": False,
        "ac_lighting_enabled": True,
        "battery_lighting_enabled": True,
        "ac_lighting_brightness": 25,
        "battery_lighting_brightness": 25,
        "ac_power_mode": None,
        "battery_power_mode": None,
        "screen_dim_sync_enabled": True,
        "controller_sleep_respect": False,
        "screen_dim_sync_mode": "off",
        "screen_dim_temp_brightness": 5,
        "idle_dim_debounce_enter_polls": 3,
        "idle_dim_debounce_exit_polls": 5,
        "idle_fade_duration_s": 0.6,
        "time_scheduler_enabled": False,
        "day_start_time": "08:00",
        "night_start_time": "20:00",
        "day_base_brightness": 40,
        "day_reactive_brightness": 50,
        "night_base_brightness": 20,
        "night_reactive_brightness": 50,
        "os_autostart_enabled": False,
        "physical_layout": "auto",
    }
    values.update(overrides)
    return SettingsValues(**values)


def test_apply_settings_values_to_config() -> None:
    cfg = SimpleNamespace()

    values = SettingsValues(
        power_management_enabled=False,
        power_off_on_suspend=False,
        power_off_on_lid_close=False,
        power_restore_on_resume=True,
        power_restore_on_lid_open=True,
        autostart=False,
        experimental_backends_enabled=True,
        ac_lighting_enabled=True,
        battery_lighting_enabled=False,
        ac_lighting_brightness=49,
        battery_lighting_brightness=51,
        ac_power_mode=PowerMode.BALANCED.value,
        battery_power_mode=None,
        screen_dim_sync_enabled=False,
        controller_sleep_respect=False,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=1,
        idle_dim_debounce_enter_polls=6,
        idle_dim_debounce_exit_polls=10,
        idle_fade_duration_s=0.8,
        time_scheduler_enabled=True,
        day_start_time="07:00",
        night_start_time="21:00",
        day_base_brightness=30,
        day_reactive_brightness=35,
        night_base_brightness=5,
        night_reactive_brightness=8,
        os_autostart_enabled=True,
        physical_layout="jis",
    )

    apply_settings_values_to_config(config=cfg, values=values)

    assert cfg.management_enabled is False
    assert cfg.power_off_on_suspend is False
    assert cfg.power_off_on_lid_close is False
    assert cfg.power_restore_on_resume is True
    assert cfg.power_restore_on_lid_open is True

    assert cfg.autostart is False
    assert cfg.os_autostart is True
    assert cfg.experimental_backends_enabled is True

    assert cfg.ac_lighting_enabled is True
    assert cfg.battery_lighting_enabled is False
    assert cfg.ac_lighting_brightness == 49
    assert cfg.battery_lighting_brightness == 50
    assert cfg.ac_power_mode == PowerMode.BALANCED.value
    assert cfg.battery_power_mode is None

    assert cfg.screen_dim_sync_enabled is False
    assert cfg.screen_dim_sync_mode == "temp"
    assert cfg.screen_dim_temp_brightness == 1
    assert cfg.idle_dim_debounce_enter_polls == 6
    assert cfg.idle_dim_debounce_exit_polls == 10
    assert cfg.idle_fade_duration_s == 0.8

    assert cfg.time_scheduler_enabled is True
    assert cfg.day_start_time == "07:00"
    assert cfg.night_start_time == "21:00"
    assert cfg.day_base_brightness == 30
    assert cfg.day_reactive_brightness == 35
    assert cfg.night_base_brightness == 5
    assert cfg.night_reactive_brightness == 8

    assert cfg.physical_layout == "jis"


def test_apply_settings_values_to_config_invalid_layout_falls_back_to_auto() -> None:
    cfg = SimpleNamespace()

    values = SettingsValues(
        power_management_enabled=True,
        power_off_on_suspend=True,
        power_off_on_lid_close=True,
        power_restore_on_resume=True,
        power_restore_on_lid_open=True,
        autostart=True,
        experimental_backends_enabled=False,
        ac_lighting_enabled=True,
        battery_lighting_enabled=True,
        ac_lighting_brightness=25,
        battery_lighting_brightness=25,
        ac_power_mode=None,
        battery_power_mode=PowerMode.PERFORMANCE.value,
        screen_dim_sync_enabled=True,
        controller_sleep_respect=False,
        screen_dim_sync_mode="off",
        screen_dim_temp_brightness=5,
        idle_dim_debounce_enter_polls=3,
        idle_dim_debounce_exit_polls=5,
        idle_fade_duration_s=0.6,
        time_scheduler_enabled=False,
        day_start_time="08:00",
        night_start_time="20:00",
        day_base_brightness=40,
        day_reactive_brightness=50,
        night_base_brightness=20,
        night_reactive_brightness=50,
        os_autostart_enabled=False,
        physical_layout="not-a-layout",
    )

    apply_settings_values_to_config(config=cfg, values=values)

    assert cfg.physical_layout == "auto"


def test_apply_settings_values_materializes_active_day_reactive_brightness(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SimpleNamespace(reactive_brightness=50)

    class FakeDateTime:
        @staticmethod
        def now() -> _datetime:
            return _datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(settings_state, "datetime", FakeDateTime)

    apply_settings_values_to_config(
        config=cfg,
        values=_settings_values(
            time_scheduler_enabled=True,
            day_start_time="08:00",
            night_start_time="20:00",
            day_reactive_brightness=42,
            night_reactive_brightness=17,
        ),
    )

    assert cfg.reactive_brightness == 42


def test_apply_settings_values_materializes_active_night_reactive_brightness(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SimpleNamespace(reactive_brightness=50)

    class FakeDateTime:
        @staticmethod
        def now() -> _datetime:
            return _datetime(2024, 1, 1, 22, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(settings_state, "datetime", FakeDateTime)

    apply_settings_values_to_config(
        config=cfg,
        values=_settings_values(
            time_scheduler_enabled=True,
            day_start_time="08:00",
            night_start_time="20:00",
            day_reactive_brightness=42,
            night_reactive_brightness=17,
        ),
    )

    assert cfg.reactive_brightness == 17


def test_internal_settings_apply_converts_default_utc_clock_to_local_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timezone

    from keyrgb.gui.settings import _settings_values as settings_values

    cfg = SimpleNamespace(reactive_brightness=50)

    class FakeUtcNow:
        def astimezone(self) -> _datetime:
            return _datetime(2024, 1, 1, 22, 0, tzinfo=timezone.utc)

    class FakeDateTime:
        @staticmethod
        def now(tz) -> FakeUtcNow:
            assert tz is timezone.utc
            return FakeUtcNow()

    monkeypatch.setattr(settings_values, "datetime", FakeDateTime)

    settings_values.apply_settings_values_to_config(
        config=cfg,
        values=_settings_values(
            time_scheduler_enabled=True,
            day_start_time="08:00",
            night_start_time="20:00",
            day_reactive_brightness=42,
            night_reactive_brightness=17,
        ),
    )

    assert cfg.reactive_brightness == 17


def test_apply_settings_values_uses_canonical_night_start_default_when_blank() -> None:
    cfg = SimpleNamespace()

    apply_settings_values_to_config(
        config=cfg,
        values=_settings_values(
            night_start_time="",
        ),
    )

    assert cfg.night_start_time == "20:00"


def test_apply_settings_values_leaves_reactive_brightness_when_scheduler_disabled() -> None:
    cfg = SimpleNamespace(reactive_brightness=50)

    apply_settings_values_to_config(
        config=cfg,
        values=_settings_values(
            time_scheduler_enabled=False,
            day_reactive_brightness=42,
            night_reactive_brightness=17,
        ),
    )

    assert cfg.reactive_brightness == 50
