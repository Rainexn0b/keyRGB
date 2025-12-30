from __future__ import annotations

from types import SimpleNamespace

from src.gui.settings.settings_state import (
    SettingsValues,
    apply_settings_values_to_config,
    clamp_brightness,
    load_settings_values,
)


def test_clamp_brightness() -> None:
    assert clamp_brightness(-1) == 0
    assert clamp_brightness(0) == 0
    assert clamp_brightness(25) == 25
    assert clamp_brightness(51) == 50


def test_load_settings_defaults_without_overrides() -> None:
    cfg = SimpleNamespace(
        brightness=30,
        battery_saver_enabled=False,
        battery_saver_brightness=10,
        # no ac/battery overrides
        power_management_enabled=True,
        power_off_on_suspend=True,
        power_off_on_lid_close=True,
        power_restore_on_resume=True,
        power_restore_on_lid_open=True,
        autostart=True,
        ac_lighting_enabled=True,
        battery_lighting_enabled=True,
    )

    values = load_settings_values(config=cfg, os_autostart_enabled=False)
    assert values.ac_lighting_brightness == 30
    assert values.battery_lighting_brightness == 30
    assert values.os_autostart_enabled is False


def test_load_settings_battery_defaults_to_battery_saver_when_enabled() -> None:
    cfg = SimpleNamespace(
        brightness=40,
        battery_saver_enabled=True,
        battery_saver_brightness=12,
    )

    values = load_settings_values(config=cfg, os_autostart_enabled=True)
    assert values.ac_lighting_brightness == 40
    assert values.battery_lighting_brightness == 12


def test_load_settings_uses_explicit_overrides_and_clamps() -> None:
    cfg = SimpleNamespace(
        brightness=25,
        battery_saver_enabled=True,
        battery_saver_brightness=12,
        ac_lighting_brightness=99,
        battery_lighting_brightness=-5,
    )

    values = load_settings_values(config=cfg, os_autostart_enabled=True)
    assert values.ac_lighting_brightness == 50
    assert values.battery_lighting_brightness == 0


def test_apply_settings_values_to_config() -> None:
    cfg = SimpleNamespace()

    values = SettingsValues(
        power_management_enabled=False,
        power_off_on_suspend=False,
        power_off_on_lid_close=False,
        power_restore_on_resume=True,
        power_restore_on_lid_open=True,
        autostart=False,
        ac_lighting_enabled=True,
        battery_lighting_enabled=False,
        ac_lighting_brightness=49,
        battery_lighting_brightness=51,
        os_autostart_enabled=True,
    )

    apply_settings_values_to_config(config=cfg, values=values)

    assert cfg.power_management_enabled is False
    assert cfg.power_off_on_suspend is False
    assert cfg.power_off_on_lid_close is False
    assert cfg.power_restore_on_resume is True
    assert cfg.power_restore_on_lid_open is True

    assert cfg.autostart is False

    assert cfg.ac_lighting_enabled is True
    assert cfg.battery_lighting_enabled is False
    assert cfg.ac_lighting_brightness == 49
    assert cfg.battery_lighting_brightness == 50
