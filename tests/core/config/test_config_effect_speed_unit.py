"""Unit tests for effect-speed configuration behavior."""

from __future__ import annotations

import logging

import pytest


def _make_config(tmp_path, monkeypatch):
    from keyrgb.core.config import Config

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    return Config()


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


def test_get_effect_speeds_returns_detached_copy(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["effect_speeds"] = {"wave": 6}

    copy_map = cfg._get_effect_speeds()

    assert copy_map == {"wave": 6}
    assert copy_map is not cfg._settings["effect_speeds"]


def test_effect_speed_snapshot_is_public_detached_copy(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["effect_speeds"] = {"wave": 6}

    copy_map = cfg.effect_speed_snapshot()

    assert copy_map == {"wave": 6}
    assert copy_map is not cfg._settings["effect_speeds"]


def test_set_effect_speed_persists_to_disk(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

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


def test_get_effect_speed_treats_explicit_none_override_as_fallback(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["speed"] = 3
    cfg._settings["effect_speeds"] = {"breathe": None}

    assert cfg.get_effect_speed("breathe") == 3


def test_set_effect_speed_replaces_non_dict_overrides_container(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)
    cfg._settings["effect_speeds"] = "bad-data"

    cfg.set_effect_speed("wave", 6)

    assert cfg._settings["effect_speeds"] == {"wave": 6}


def test_set_effect_speed_raises_type_error_for_non_string_effect_name(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    try:
        cfg.set_effect_speed(object(), 7)
    except TypeError as exc:
        assert str(exc) == "effect_name must be a str"
    else:
        raise AssertionError("TypeError was not raised")


def test_set_effect_speed_raises_and_rolls_back_on_io_failures(tmp_path, monkeypatch, caplog) -> None:
    from keyrgb.core.config import ConfigPersistenceError, file_storage

    cfg = _make_config(tmp_path, monkeypatch)
    original_speeds = dict(cfg._settings.get("effect_speeds") or {})

    monkeypatch.setattr(file_storage.os, "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")))

    with (
        caplog.at_level(logging.WARNING, logger="keyrgb.core.config.config"),
        pytest.raises(ConfigPersistenceError, match="Could not persist configuration"),
    ):
        cfg.set_effect_speed("wave", 7)

    assert cfg._settings.get("effect_speeds") == original_speeds
    assert cfg._settings == cfg._persisted_settings
    records = [record for record in caplog.records if "Failed to save config" in record.getMessage()]
    assert records
    assert records[-1].exc_info is not None


def test_set_effect_speed_propagates_non_io_save_failures(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    monkeypatch.setattr(cfg, "_save", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    try:
        cfg.set_effect_speed("wave", 7)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("RuntimeError was not raised")

    assert cfg._settings["effect_speeds"]["wave"] == 7
