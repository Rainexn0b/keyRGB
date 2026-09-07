from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import ClassVar

import pytest

from keyrgb.core.config._settings_view import ConfigSettingsView
from keyrgb.core.diagnostics.model import DiagnosticsConfigSnapshot
from keyrgb.core.power.system import PowerMode
from keyrgb.gui.settings.settings_state import (
    clamp_brightness,
    clamp_nonzero_brightness,
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
        reactive_brightness=18,
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
    assert values.ac_power_mode is None
    assert values.battery_power_mode is None
    assert values.os_autostart_enabled is False
    assert values.experimental_backends_enabled is False
    assert values.screen_dim_sync_enabled is True
    assert values.screen_dim_sync_mode in {"off", "temp"}
    assert clamp_nonzero_brightness(values.screen_dim_temp_brightness) == values.screen_dim_temp_brightness
    assert values.day_base_brightness == 30
    assert values.day_reactive_brightness == 18
    assert values.night_base_brightness == 30
    assert values.night_reactive_brightness == 18


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


def test_load_settings_reads_optional_power_source_modes() -> None:
    cfg = SimpleNamespace(
        brightness=25,
        battery_saver_enabled=False,
        battery_saver_brightness=12,
        ac_power_mode=" Balanced ",
        battery_power_mode="invalid",
    )

    values = load_settings_values(config=cfg, os_autostart_enabled=True)

    assert values.ac_power_mode == PowerMode.BALANCED.value
    assert values.battery_power_mode is None


def test_load_settings_malformed_property_and_coercion_values_fall_back_safely(caplog) -> None:
    class ExplodingBool:
        def __bool__(self) -> bool:
            raise RuntimeError("boom")

    class ExplodingInt:
        def __int__(self) -> int:
            raise RuntimeError("boom")

    class Config:
        brightness = 30
        battery_saver_enabled = False
        battery_saver_brightness = 12
        experimental_backends_enabled = ExplodingBool()
        ac_lighting_brightness = ExplodingInt()
        screen_dim_temp_brightness = ExplodingInt()

        @property
        def autostart(self) -> bool:
            raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="keyrgb.gui.settings.settings_state"):
        values = load_settings_values(config=Config(), os_autostart_enabled=True)

    assert values.autostart is True
    assert values.experimental_backends_enabled is False
    assert values.ac_lighting_brightness == 30
    assert values.screen_dim_temp_brightness == 5
    assert "Failed reading settings attribute 'autostart'" in caplog.text
    assert "Failed coercing settings attribute 'experimental_backends_enabled' to bool" in caplog.text
    assert "Failed coercing settings value to int" in caplog.text
    assert "Failed reading settings integer attribute 'screen_dim_temp_brightness'" in caplog.text


def test_load_settings_propagates_unexpected_programming_errors() -> None:
    class ExplodingBool:
        def __bool__(self) -> bool:
            raise AssertionError("boom")

    class Config:
        brightness = 30
        battery_saver_enabled = False
        battery_saver_brightness = 12
        experimental_backends_enabled = ExplodingBool()

    with pytest.raises(AssertionError):
        load_settings_values(config=Config(), os_autostart_enabled=True)


def test_load_settings_malformed_string_values_fall_back_safely(caplog) -> None:
    class ExplodingString:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    class Config:
        brightness = 30
        battery_saver_enabled = False
        battery_saver_brightness = 12
        screen_dim_sync_mode = ExplodingString()

        @property
        def physical_layout(self) -> str:
            raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="keyrgb.gui.settings.settings_state"):
        values = load_settings_values(config=Config(), os_autostart_enabled=True)

    assert values.screen_dim_sync_mode == "off"
    assert values.physical_layout == "auto"
    assert "Failed coercing settings attribute 'screen_dim_sync_mode' to normalized string" in caplog.text
    assert "Failed reading settings attribute 'physical_layout'" in caplog.text


def test_load_settings_prefers_typed_settings_view_when_available() -> None:
    class Config:
        def settings_view(self) -> ConfigSettingsView:
            return ConfigSettingsView.from_mapping(
                {
                    "brightness": 40,
                    "battery_saver_enabled": True,
                    "battery_saver_brightness": 11,
                    "autostart": False,
                    "experimental_backends_enabled": True,
                    "screen_dim_sync_mode": "TEMP",
                    "physical_layout": "JIS",
                }
            )

        @property
        def brightness(self) -> int:
            raise AssertionError("typed settings_view path should avoid raw attribute reads")

    values = load_settings_values(config=Config(), os_autostart_enabled=True)

    assert values.ac_lighting_brightness == 40
    assert values.battery_lighting_brightness == 11
    assert values.autostart is False
    assert values.experimental_backends_enabled is True
    assert values.screen_dim_sync_mode == "temp"
    assert values.physical_layout == "jis"


def test_load_settings_accepts_direct_config_settings_view() -> None:
    values = load_settings_values(
        config=ConfigSettingsView.from_mapping(
            {
                "brightness": 37,
                "battery_saver_enabled": True,
                "battery_saver_brightness": 9,
                "experimental_backends_enabled": True,
                "screen_dim_sync_mode": "TEMP",
            }
        ),
        os_autostart_enabled=False,
    )

    assert values.ac_lighting_brightness == 37
    assert values.battery_lighting_brightness == 9
    assert values.experimental_backends_enabled is True
    assert values.screen_dim_sync_mode == "temp"


def test_load_settings_uses_settings_mapping_when_settings_view_method_is_absent() -> None:
    class Config:
        settings: ClassVar[dict] = {
            "brightness": 41,
            "battery_saver_enabled": True,
            "battery_saver_brightness": 13,
            "power_off_on_suspend": False,
            "physical_layout": "JIS",
        }

        @property
        def brightness(self) -> int:
            raise AssertionError("settings mapping path should avoid raw attribute reads")

    values = load_settings_values(config=Config(), os_autostart_enabled=True)

    assert values.ac_lighting_brightness == 41
    assert values.battery_lighting_brightness == 13
    assert values.power_off_on_suspend is False
    assert values.physical_layout == "jis"


def test_load_settings_accepts_diagnostics_snapshot_settings_mapping() -> None:
    class Config:
        settings = DiagnosticsConfigSnapshot(
            settings={
                "brightness": 19,
                "ac_lighting_brightness": 28,
                "battery_lighting_brightness": 7,
                "power_off_on_lid_close": False,
            }
        ).settings

    values = load_settings_values(config=Config(), os_autostart_enabled=False)

    assert values.ac_lighting_brightness == 28
    assert values.battery_lighting_brightness == 7
    assert values.power_off_on_lid_close is False


def test_load_settings_scheduler_defaults_follow_live_brightness_when_view_keys_are_absent() -> None:
    class Config:
        def settings_view(self) -> ConfigSettingsView:
            return ConfigSettingsView.from_mapping(
                {
                    "brightness": 33,
                    "reactive_brightness": 14,
                    "time_scheduler_enabled": True,
                }
            )

    values = load_settings_values(config=Config(), os_autostart_enabled=False)

    assert values.day_base_brightness == 33
    assert values.day_reactive_brightness == 14
    assert values.night_base_brightness == 33
    assert values.night_reactive_brightness == 14


def test_load_settings_accepts_direct_diagnostics_config_snapshot() -> None:
    values = load_settings_values(
        config=DiagnosticsConfigSnapshot(
            settings={
                "brightness": 26,
                "battery_saver_enabled": True,
                "battery_saver_brightness": 8,
                "physical_layout": "JIS",
            }
        ),
        os_autostart_enabled=False,
    )

    assert values.ac_lighting_brightness == 26
    assert values.battery_lighting_brightness == 8
    assert values.physical_layout == "jis"


def test_load_settings_partial_typed_view_falls_back_to_raw_attributes() -> None:
    """Verify that partial ConfigSettingsView keys fall back to raw config attributes.

    This seam test ensures the typed-loader consolidation works correctly when:
    - A ConfigSettingsView exists with some (but not all) settings
    - Missing keys should fall back to raw config attributes
    - The fallback mechanism is properly integrated in _SettingsReader
    """

    class Config:
        # Settings provided via typed view (partial)
        def settings_view(self) -> ConfigSettingsView:
            return ConfigSettingsView.from_mapping(
                {
                    "brightness": 35,
                    "battery_saver_enabled": True,
                    # Note: missing battery_saver_brightness, power_management_enabled, etc.
                }
            )

        # Fallback raw attributes for missing keys
        battery_saver_brightness = 20
        power_management_enabled = False
        power_off_on_suspend = False
        power_off_on_lid_close = True
        power_restore_on_resume = True
        power_restore_on_lid_open = False
        autostart = True
        experimental_backends_enabled = False
        ac_lighting_enabled = True
        battery_lighting_enabled = False
        screen_dim_sync_enabled = False
        physical_layout = "DVORAK"

    values = load_settings_values(config=Config(), os_autostart_enabled=False)

    # From typed ConfigSettingsView
    assert values.ac_lighting_brightness == 35  # base brightness from typed view
    assert values.battery_lighting_brightness == 20  # battery_saver_brightness from fallback

    # From raw config fallback (keys not in ConfigSettingsView)
    assert values.power_management_enabled is False
    assert values.power_off_on_suspend is False
    assert values.power_off_on_lid_close is True
    assert values.power_restore_on_resume is True
    assert values.power_restore_on_lid_open is False

    # Optional keys: if not in view and not in raw config, use defaults
    assert values.screen_dim_sync_enabled is False  # from raw config fallback
    # physical_layout from raw config fallback, normalized
    assert values.physical_layout == "dvorak"
