#!/usr/bin/env python3
"""Unit tests for core/config.py.

Focuses on small behaviors that should not depend on real user config.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def _make_config(tmp_path, monkeypatch):
    from src.core.config import Config

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

    from src.core.config import Config

    cfg2 = Config()
    assert cfg2.experimental_backends_enabled is True


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


def test_reload_skips_disk_load_when_mtime_is_unchanged(tmp_path, monkeypatch) -> None:
    from src.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)
    cfg._last_reload_mtime_ns = 123
    load_calls = {"count": 0}

    monkeypatch.setattr(Config, "_load", lambda self: load_calls.__setitem__("count", load_calls["count"] + 1) or {})
    monkeypatch.setattr(Path, "stat", lambda self, *args, **kwargs: SimpleNamespace(st_mtime_ns=123, st_mode=0o100644))

    cfg.reload()

    assert load_calls["count"] == 0


def test_reload_replaces_settings_when_file_mtime_changes(tmp_path, monkeypatch) -> None:
    from src.core.config import Config

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
    assert cfg.reactive_use_manual_color is False


def test_reactive_color_per_key_colors_and_screen_dim_props_normalize_values(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["reactive_color"] = ("12", "999", "bad")

    assert cfg.reactive_color == (12, 255, 0)

    cfg.per_key_colors = {(1, 2): (3, 4, 5)}
    assert cfg._settings["per_key_colors"] == {"1,2": [3, 4, 5]}
    assert cfg.per_key_colors == {(1, 2): (3, 4, 5)}

    cfg.screen_dim_sync_mode = "TEMP"
    assert cfg.screen_dim_sync_mode == "temp"

    cfg.screen_dim_sync_mode = "invalid"
    assert cfg.screen_dim_sync_mode == "off"

    cfg.screen_dim_temp_brightness = 0
    assert cfg.screen_dim_temp_brightness == 1


def test_physical_layout_enum_prop(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.physical_layout in ("auto", "ansi", "iso", "ks", "abnt", "jis")

    cfg.physical_layout = "ansi"
    assert cfg.physical_layout == "ansi"

    cfg.physical_layout = "ISO"
    assert cfg.physical_layout == "iso"

    cfg.physical_layout = "ks"
    assert cfg.physical_layout == "ks"

    cfg.physical_layout = "ABNT"
    assert cfg.physical_layout == "abnt"

    cfg.physical_layout = "jis"
    assert cfg.physical_layout == "jis"

    cfg.physical_layout = "invalid"
    assert cfg.physical_layout == "auto"


def test_effect_speed_and_return_effect_setters_normalize_values(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    cfg.effect = "WAVE"
    assert cfg.effect == "wave"

    cfg.speed = 99
    assert cfg.speed == 10

    cfg.speed = -5
    assert cfg.speed == 0

    cfg.return_effect_after_effect = None
    assert cfg.return_effect_after_effect is None

    cfg.return_effect_after_effect = "   "
    assert cfg.return_effect_after_effect is None

    cfg._settings["return_effect_after_effect"] = "   "
    assert cfg.return_effect_after_effect is None

    cfg.return_effect_after_effect = " PERKEY "
    assert cfg.return_effect_after_effect == "perkey"

    class BadString:
        def __str__(self):
            raise RuntimeError("boom")

    cfg._settings["return_effect_after_effect"] = BadString()
    assert cfg.return_effect_after_effect is None


def test_brightness_color_and_direction_accessors_cover_fallback_paths(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    class BadString:
        def __str__(self):
            raise RuntimeError("boom")

    cfg._settings["effect"] = BadString()
    cfg._settings["brightness"] = "11"
    assert cfg.brightness == 11

    monkeypatch.setattr(cfg, "_normalize_brightness_value", lambda value: 17)

    cfg.brightness = 42
    assert cfg._settings["brightness"] == 17

    cfg.effect_brightness = 42
    assert cfg.effect_brightness == 17

    cfg.perkey_brightness = 42
    assert cfg.perkey_brightness == 17

    cfg.reactive_brightness = 42
    assert cfg.reactive_brightness == 17

    cfg.color = (1, 2, 3)
    assert cfg.color == (1, 2, 3)

    assert cfg.direction is None
    cfg._settings["direction"] = " UP_LEFT "
    assert cfg.direction == "up_left"

    cfg._settings["direction"] = "   "
    assert cfg.direction is None

    cfg.direction = "Down_Right"
    assert cfg.direction == "down_right"


def test_reactive_color_defaults_and_manual_toggle_cover_defensive_paths(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    class BrokenDefaults:
        def get(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    cfg.DEFAULTS = BrokenDefaults()
    cfg._settings["reactive_color"] = None
    assert cfg.reactive_color == (255, 255, 255)


def test_get_effect_speed_returns_per_effect_when_set(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["speed"] = 4

    cfg.set_effect_speed("breathe", 7)

    assert cfg.get_effect_speed("breathe") == 7
    # Other effects still fall back to global.
    assert cfg.get_effect_speed("wave") == 4


def test_get_effect_speed_falls_back_to_global_when_no_override(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["speed"] = 6
    cfg._settings["effect_speeds"] = {}

    assert cfg.get_effect_speed("rainbow_swirl") == 6


def test_set_effect_speed_clamps_value(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg.set_effect_speed("twinkle", 99)
    assert cfg.get_effect_speed("twinkle") == 10

    cfg.set_effect_speed("twinkle", -5)
    assert cfg.get_effect_speed("twinkle") == 0


def test_set_effect_speed_persists_to_disk(tmp_path, monkeypatch) -> None:
    from src.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)
    cfg.set_effect_speed("fire", 8)

    cfg2 = Config()
    assert cfg2.get_effect_speed("fire") == 8


def test_get_effect_speed_ignores_corrupt_effect_speeds(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["speed"] = 5
    cfg._settings["effect_speeds"] = "not-a-dict"

    # Should fall back to global without raising.
    assert cfg.get_effect_speed("breathe") == 5


    cfg.reactive_color = ("9", "10", "bad")
    assert cfg._settings["reactive_color"] == [9, 10, 0]

    cfg.reactive_use_manual_color = 1
    assert cfg.reactive_use_manual_color is True
