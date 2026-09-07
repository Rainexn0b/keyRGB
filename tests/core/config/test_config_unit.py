#!/usr/bin/env python3
"""Unit tests for core/config.py.

Focuses on small behaviors that should not depend on real user config.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from keyrgb.core.config._settings_view import ConfigSettingsView
from keyrgb.core.power.system import PowerMode


def _make_config(tmp_path, monkeypatch):
    from keyrgb.core.config import Config

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    return Config()


def test_return_effect_after_effect_sanitizes_invalid_values(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    # Simulate a broken/unknown persisted value.
    cfg._settings["return_effect_after_effect"] = "totally-not-a-mode"
    assert cfg.return_effect_after_effect is None

    # Known values should pass through, normalized.
    cfg._settings["return_effect_after_effect"] = "PERKEY"
    assert cfg.return_effect_after_effect == "perkey"

    cfg._settings["return_effect_after_effect"] = "perkey_pulse"
    assert cfg.return_effect_after_effect is None


def test_experimental_backends_enabled_persists(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    assert cfg.experimental_backends_enabled is False

    cfg.experimental_backends_enabled = True

    from keyrgb.core.config import Config

    cfg2 = Config()
    assert cfg2.experimental_backends_enabled is True


def test_system_power_extreme_cap_khz_persists_and_clamps(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)
    assert cfg.system_power_extreme_cap_khz == 800000

    cfg.system_power_extreme_cap_khz = 123456
    assert cfg.system_power_extreme_cap_khz == 400000

    cfg.system_power_extreme_cap_khz = 1300000
    assert cfg.system_power_extreme_cap_khz == 1300000

    cfg2 = Config()
    assert cfg2.system_power_extreme_cap_khz == 1300000


def test_new_config_uses_power_source_policy_defaults(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.ac_lighting_enabled is True
    assert cfg.ac_lighting_brightness == 40
    assert cfg.ac_power_mode == PowerMode.PERFORMANCE.value

    assert cfg.battery_lighting_enabled is True
    assert cfg.battery_lighting_brightness == 20
    assert cfg.battery_power_mode == PowerMode.BALANCED.value


def test_brightness_property_tracks_effect_mode_without_overwriting_other_mode(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["brightness"] = 35
    cfg._settings["perkey_brightness"] = 15
    cfg._settings["effect"] = "perkey"

    assert cfg.brightness == 15

    cfg.brightness = 18

    assert cfg._settings["perkey_brightness"] == 20
    assert cfg._settings["brightness"] == 35

    cfg._settings["effect"] = "wave"
    cfg.brightness = 12

    assert cfg._settings["brightness"] == 10
    assert cfg._settings["perkey_brightness"] == 20


def test_brightness_property_uses_rendered_perkey_state_for_saved_base_map(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["effect"] = "none"
    cfg._settings["brightness"] = 35
    cfg._settings["perkey_brightness"] = 15
    cfg._settings["per_key_colors"] = {"0,0": [1, 2, 3]}

    assert cfg.brightness == 15
    assert cfg.effect_brightness == 35

    cfg.brightness = 18

    assert cfg._settings["perkey_brightness"] == 20
    assert cfg._settings["brightness"] == 35
    assert cfg.effect_brightness == 35


def test_reload_skips_disk_load_when_mtime_is_unchanged(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)
    cfg._last_reload_mtime_ns = 123
    load_calls = {"count": 0}

    monkeypatch.setattr(Config, "_load", lambda self: load_calls.__setitem__("count", load_calls["count"] + 1) or {})
    monkeypatch.setattr(Path, "stat", lambda self, *args, **kwargs: SimpleNamespace(st_mtime_ns=123, st_mode=0o100644))

    cfg.reload()

    assert load_calls["count"] == 0


def test_reload_replaces_settings_when_file_mtime_changes(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["effect"] = "rainbow"
    cfg._last_reload_mtime_ns = 123

    monkeypatch.setattr(
        Config,
        "_load",
        lambda self: {
            "effect": "wave",
            "brightness": 30,
            "perkey_brightness": 25,
        },
    )
    monkeypatch.setattr(Path, "stat", lambda self, *args, **kwargs: SimpleNamespace(st_mtime_ns=456, st_mode=0o100644))

    cfg.reload()

    assert cfg._settings == {
        "effect": "wave",
        "brightness": 30,
        "perkey_brightness": 25,
    }
    assert cfg._last_reload_mtime_ns == 456


def test_reactive_and_optional_brightness_getters_fall_back_safely(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["brightness"] = 22
    cfg._settings["reactive_brightness"] = object()
    cfg._settings["ac_lighting_brightness"] = "13"
    cfg._settings["battery_lighting_brightness"] = "bad"
    cfg._settings["ac_perkey_profile_name"] = "  gaming  "
    cfg._settings["battery_perkey_profile_name"] = object()

    class BadBool:
        def __bool__(self):
            raise RuntimeError("boom")

    cfg._settings["reactive_use_manual_color"] = BadBool()
    monkeypatch.setattr(
        cfg,
        "_normalize_brightness_value",
        lambda value: 15 if value == "13" else (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert cfg.reactive_brightness == 22
    assert cfg.ac_lighting_brightness == 15
    assert cfg.battery_lighting_brightness is None
    assert cfg.ac_perkey_profile_name == "gaming"
    assert cfg.battery_perkey_profile_name is not None
    assert cfg.reactive_use_manual_color is False


def test_ac_battery_perkey_profile_props_persist_and_normalize(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.ac_perkey_profile_name is None
    assert cfg.battery_perkey_profile_name is None

    cfg.ac_perkey_profile_name = " Gaming "
    cfg.battery_perkey_profile_name = " battery "

    assert cfg.ac_perkey_profile_name == "Gaming"
    assert cfg.battery_perkey_profile_name == "battery"

    cfg2 = Config()
    assert cfg2.ac_perkey_profile_name == "Gaming"
    assert cfg2.battery_perkey_profile_name == "battery"

    cfg.ac_perkey_profile_name = ""
    assert cfg.ac_perkey_profile_name is None


def test_settings_view_exposes_readonly_typed_snapshot(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["brightness"] = "27"

    view = cfg.settings_view()

    assert isinstance(view, ConfigSettingsView)
    assert view.read_int("brightness", 0) == 27
    with pytest.raises(TypeError):
        view["brightness"] = 5  # type: ignore[index]
