from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.config._lighting._coercion import (
    _clamp_rgb_channel,
    coerce_loaded_settings,
    normalize_brightness_value,
    normalize_precise_brightness_value,
    normalize_rgb_triplet,
    normalize_trail_percent_value,
)
from src.core.config._lighting._props import bool_prop, enum_prop, int_prop, optional_brightness_prop


def test_normalize_brightness_value_handles_invalid_zero_and_low_nonzero_values() -> None:
    assert normalize_brightness_value(object()) == 0
    assert normalize_brightness_value(0) == 0
    assert normalize_brightness_value(1) == 5


def test_normalize_precise_brightness_value_preserves_nonzero_single_steps() -> None:
    assert normalize_precise_brightness_value(object()) == 0
    assert normalize_precise_brightness_value(-1) == 0
    assert normalize_precise_brightness_value(1) == 1
    assert normalize_precise_brightness_value(42) == 42
    assert normalize_precise_brightness_value(99) == 50


def test_normalize_trail_percent_value_clamps_and_defaults() -> None:
    assert normalize_trail_percent_value(object()) == 50
    assert normalize_trail_percent_value(0) == 1
    assert normalize_trail_percent_value(-5) == 1
    assert normalize_trail_percent_value(1) == 1
    assert normalize_trail_percent_value(50) == 50
    assert normalize_trail_percent_value(100) == 100
    assert normalize_trail_percent_value(200) == 100


def test_normalize_rgb_triplet_falls_back_to_default_when_value_is_not_iterable() -> None:
    assert normalize_rgb_triplet(object(), default=(1, 2, 3)) == (1, 2, 3)


def test_clamp_rgb_channel_covers_bool_float_string_invalid_and_clamping_paths() -> None:
    assert _clamp_rgb_channel(True) == 1
    assert _clamp_rgb_channel(12.9) == 12
    assert _clamp_rgb_channel("12.4") == 12
    assert _clamp_rgb_channel("bad") == 0
    assert _clamp_rgb_channel(object()) == 0
    assert _clamp_rgb_channel(999) == 255


def test_coerce_loaded_settings_populates_missing_perkey_and_normalizes_overrides(tmp_path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"brightness": 1}), encoding="utf-8")

    settings = {
        "brightness": 1,
        "ac_lighting_brightness": "13",
        "battery_lighting_brightness": 49,
    }
    save_calls: list[str] = []

    coerce_loaded_settings(
        settings=settings,
        config_file=config_file,
        save_fn=lambda: save_calls.append("saved"),
    )

    assert settings["brightness"] == 5
    assert settings["perkey_brightness"] == 5
    assert settings["ac_lighting_brightness"] == 15
    assert settings["battery_lighting_brightness"] == 50
    assert save_calls == ["saved"]


def test_coerce_loaded_settings_normalizes_existing_perkey_value_when_present_on_disk(tmp_path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"perkey_brightness": 11}), encoding="utf-8")

    settings = {
        "brightness": 20,
        "perkey_brightness": 11,
    }
    save_calls: list[str] = []

    coerce_loaded_settings(
        settings=settings,
        config_file=config_file,
        save_fn=lambda: save_calls.append("saved"),
    )

    assert settings["brightness"] == 20
    assert settings["perkey_brightness"] == 10
    assert save_calls == ["saved"]


def test_coerce_loaded_settings_preserves_precise_reactive_brightness_when_present(tmp_path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"reactive_brightness": 11}), encoding="utf-8")

    settings = {
        "brightness": 20,
        "reactive_brightness": 11,
    }
    save_calls: list[str] = []

    coerce_loaded_settings(
        settings=settings,
        config_file=config_file,
        save_fn=lambda: save_calls.append("saved"),
    )

    assert settings["brightness"] == 20
    assert settings["perkey_brightness"] == 20
    assert settings["reactive_brightness"] == 11
    assert save_calls == ["saved"]


def test_coerce_loaded_settings_normalizes_out_of_range_trail_percent(tmp_path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"reactive_trail_percent": 200}), encoding="utf-8")

    settings = {
        "brightness": 20,
        "reactive_trail_percent": 200,
    }
    save_calls: list[str] = []

    coerce_loaded_settings(
        settings=settings,
        config_file=config_file,
        save_fn=lambda: save_calls.append("saved"),
    )

    assert settings["reactive_trail_percent"] == 100
    assert save_calls == ["saved"]


def test_coerce_loaded_settings_skips_trail_percent_when_absent(tmp_path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"brightness": 20}), encoding="utf-8")

    settings: dict = {"brightness": 20}
    coerce_loaded_settings(
        settings=settings,
        config_file=config_file,
        save_fn=lambda: None,
    )

    assert "reactive_trail_percent" not in settings


def test_coerce_loaded_settings_swallows_save_failures() -> None:
    settings = {"brightness": "bad"}

    coerce_loaded_settings(
        settings=settings,
        config_file=Path("/definitely/missing/keyrgb-config.json"),
        save_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert settings["brightness"] == 0
    assert settings["perkey_brightness"] == 0


def test_coerce_loaded_settings_tolerates_malformed_json_on_disk(tmp_path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text("{not valid json", encoding="utf-8")

    settings = {"brightness": 1}
    save_calls: list[str] = []

    coerce_loaded_settings(
        settings=settings,
        config_file=config_file,
        save_fn=lambda: save_calls.append("saved"),
    )

    assert settings["brightness"] == 5
    assert settings["perkey_brightness"] == 5
    assert save_calls == ["saved"]


def test_bool_prop_returns_default_and_logs_when_settings_access_raises(caplog) -> None:
    class BrokenSettings(dict):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    class Holder:
        enabled = bool_prop("enabled", default=True)

        def __init__(self) -> None:
            self._settings = BrokenSettings()
            self.save_calls = 0

        def _save(self) -> None:
            self.save_calls += 1

    holder = Holder()

    with caplog.at_level(logging.ERROR):
        assert holder.enabled is True

    assert "Failed reading config setting enabled" in caplog.text
    holder.enabled = False
    assert holder._settings["enabled"] is False
    assert holder.save_calls == 1


def test_int_prop_getter_and_setter_fall_back_to_default_on_bad_values() -> None:
    class Holder:
        level = int_prop("level", default=7, min_v=1, max_v=9)

        def __init__(self) -> None:
            self._settings = {"level": object()}
            self.save_calls = 0

        def _save(self) -> None:
            self.save_calls += 1

    holder = Holder()

    assert holder.level == 7

    holder.level = object()
    assert holder._settings["level"] == 7
    assert holder.save_calls == 1


def test_int_prop_logs_when_user_defined_int_coercion_raises_runtime_error(caplog) -> None:
    class BadInt:
        def __int__(self) -> int:
            raise RuntimeError("boom")

    class Holder:
        level = int_prop("level", default=7, min_v=1, max_v=9)

        def __init__(self) -> None:
            self._settings = {"level": BadInt()}
            self.save_calls = 0

        def _save(self) -> None:
            self.save_calls += 1

    holder = Holder()

    with caplog.at_level(logging.ERROR):
        assert holder.level == 7
        holder.level = BadInt()

    assert caplog.text.count("Failed coercing config int value") == 2
    assert holder._settings["level"] == 7
    assert holder.save_calls == 1


def test_enum_prop_uses_allowed_fallback_when_default_is_invalid() -> None:
    class Holder:
        mode = enum_prop("mode", default="invalid", allowed=["one", "two"])

        def __init__(self) -> None:
            self._settings: dict[str, str] = {}
            self.save_calls = 0

        def _save(self) -> None:
            self.save_calls += 1

    holder = Holder()
    default_mode = holder.mode

    assert default_mode in {"one", "two"}

    holder.mode = "bad"

    assert holder.mode == default_mode
    assert holder.save_calls == 1


def test_optional_brightness_prop_handles_getter_failure_and_none_setter(caplog) -> None:
    class Holder:
        brightness_override = optional_brightness_prop("brightness_override")

        def __init__(self) -> None:
            self._settings = {"brightness_override": object()}
            self.save_calls = 0

        def _normalize_brightness_value(self, _value: object) -> int:
            raise RuntimeError("boom")

        def _save(self) -> None:
            self.save_calls += 1

    holder = Holder()

    with caplog.at_level(logging.ERROR):
        assert holder.brightness_override is None

    assert "Failed normalizing optional brightness value" in caplog.text

    holder.brightness_override = None
    assert holder._settings["brightness_override"] is None
    assert holder.brightness_override is None

    holder._normalize_brightness_value = lambda value: 17  # type: ignore[method-assign]
    holder._settings["brightness_override"] = 42
    assert holder.brightness_override == 17
    holder.brightness_override = 42
    assert holder._settings["brightness_override"] == 17
    assert holder.save_calls == 2
