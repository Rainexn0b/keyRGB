#!/usr/bin/env python3
"""Unit tests for core/config secondary/layout/software-target accessors.

Split from test_config_unit.py to keep files under 450 lines.
"""

from __future__ import annotations


def _make_config(tmp_path, monkeypatch):
    from keyrgb.core.config import Config

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    return Config()


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


def test_idle_fade_duration_float_prop_normalizes_and_clamps(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.idle_fade_duration_s == 0.6

    cfg.idle_fade_duration_s = 1.2
    assert cfg.idle_fade_duration_s == 1.2
    assert cfg._settings["idle_fade_duration_s"] == 1.2

    cfg.idle_fade_duration_s = 0.0
    assert cfg.idle_fade_duration_s == 0.1

    cfg.idle_fade_duration_s = 99.0
    assert cfg.idle_fade_duration_s == 3.0

    cfg._settings["idle_fade_duration_s"] = "fast"
    assert cfg.idle_fade_duration_s == 0.6


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


def test_layout_legend_pack_persists_and_normalizes(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.layout_legend_pack == "auto"

    cfg.layout_legend_pack = "ISO-DE-QWERTZ"
    assert cfg.layout_legend_pack == "iso-de-qwertz"

    cfg2 = Config()
    assert cfg2.layout_legend_pack == "iso-de-qwertz"

    cfg.layout_legend_pack = "invalid-pack"
    assert cfg.layout_legend_pack == "auto"


def test_tray_device_context_persists_and_normalizes(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.tray_device_context == "keyboard"

    cfg.tray_device_context = " LightBar:048D:7001 "
    assert cfg.tray_device_context == "lightbar:048d:7001"

    cfg2 = Config()
    assert cfg2.tray_device_context == "lightbar:048d:7001"

    cfg._settings["tray_device_context"] = object()
    assert cfg.tray_device_context == "keyboard"


def test_lightbar_color_and_brightness_persist_independently(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.lightbar_brightness == 25
    assert cfg.lightbar_color == (255, 0, 0)

    cfg.lightbar_brightness = 17
    cfg.lightbar_color = ("9", "10", "bad")

    assert cfg.lightbar_brightness == 17
    assert cfg.lightbar_color == (9, 10, 0)

    cfg2 = Config()
    assert cfg2.lightbar_brightness == 17
    assert cfg2.lightbar_color == (9, 10, 0)


def test_secondary_device_state_persists_for_generic_aux_routes(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)

    cfg.set_secondary_device_brightness("mouse", 17)
    cfg.set_secondary_device_color("mouse", ("1", "bad", "99"))

    assert cfg.get_secondary_device_brightness("mouse") == 17
    assert cfg.get_secondary_device_color("mouse") == (1, 0, 99)

    cfg2 = Config()
    assert cfg2.get_secondary_device_brightness("mouse") == 17
    assert cfg2.get_secondary_device_color("mouse") == (1, 0, 99)


def test_secondary_device_brightness_prefers_first_compatibility_key(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    cfg.DEFAULTS = {"legacy_primary": 5, "legacy_secondary": 10}
    cfg._settings["legacy_primary"] = 42
    cfg._settings["legacy_secondary"] = 17

    assert (
        cfg.get_secondary_device_brightness(
            "mouse",
            fallback_keys=("legacy_primary", "legacy_secondary"),
            default=0,
        )
        == 42
    )


def test_secondary_device_color_uses_default_fallback_keys_in_order(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    cfg.DEFAULTS = {"legacy_secondary": [4, 5, 6]}

    assert cfg.get_secondary_device_color(
        "mouse",
        fallback_keys=("legacy_primary", "legacy_secondary"),
        default=(255, 0, 0),
    ) == (4, 5, 6)


def test_software_effect_target_persists_and_normalizes(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    cfg = _make_config(tmp_path, monkeypatch)

    assert cfg.software_effect_target == "keyboard"

    cfg.software_effect_target = "ALL_UNIFORM_CAPABLE"
    assert cfg.software_effect_target == "all_uniform_capable"

    cfg2 = Config()
    assert cfg2.software_effect_target == "all_uniform_capable"

    cfg.software_effect_target = "invalid"
    assert cfg.software_effect_target == "keyboard"


def test_brightness_color_and_direction_accessors_cover_fallback_paths(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    class BadString:
        def __str__(self):
            raise RuntimeError("boom")

    cfg._settings["effect"] = BadString()
    cfg._settings["brightness"] = "11"
    assert cfg.brightness == 11
    # Invalid in-memory effect values must not block later property reads; restore a
    # serializable value before exercising setters that persist.
    cfg._settings["effect"] = "none"

    monkeypatch.setattr(cfg, "_normalize_brightness_value", lambda value: 17)

    cfg.brightness = 42
    assert cfg._settings["brightness"] == 17

    cfg.effect_brightness = 42
    assert cfg.effect_brightness == 17

    cfg.perkey_brightness = 42
    assert cfg.perkey_brightness == 17

    monkeypatch.setattr(cfg, "_normalize_reactive_brightness_value", lambda value: 13)
    cfg.reactive_brightness = 42
    assert cfg.reactive_brightness == 13

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
    cfg._settings["reactive_visual_mode"] = "LOUD"
    assert cfg.reactive_color == (255, 255, 255)
    assert cfg.reactive_visual_mode == "subtle"
    cfg.reactive_visual_mode = "VIVID"
    assert cfg.reactive_visual_mode == "vivid"
