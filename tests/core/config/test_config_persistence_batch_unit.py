"""Unit tests for configuration persistence and batch updates."""

from __future__ import annotations

import logging

import pytest


def _make_config(tmp_path, monkeypatch):
    from keyrgb.core.config import Config

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    return Config()


def test_lightbar_color_falls_back_and_logs_when_defaults_lookup_raises(tmp_path, monkeypatch, caplog) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    class BrokenDefaults:
        def get(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    cfg.DEFAULTS = BrokenDefaults()
    cfg._settings["lightbar_color"] = None

    with caplog.at_level(logging.ERROR, logger="keyrgb.core.config.config"):
        assert cfg.lightbar_color == (255, 0, 0)

    records = [
        record for record in caplog.records if "Failed to read config default 'lightbar_color'" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_lightbar_color_propagates_unexpected_defaults_lookup_failures(tmp_path, monkeypatch) -> None:
    cfg = _make_config(tmp_path, monkeypatch)

    class BrokenDefaults:
        def get(self, *_args, **_kwargs):
            raise AssertionError("unexpected defaults bug")

    cfg.DEFAULTS = BrokenDefaults()
    cfg._settings["lightbar_color"] = None

    with pytest.raises(AssertionError, match="unexpected defaults bug"):
        _ = cfg.lightbar_color


def test_stale_config_instances_merge_unrelated_updates(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    first = Config()
    stale_second = Config()

    first.brightness = 17
    stale_second.effect = "rainbow_wave"

    reloaded = Config()
    assert reloaded.brightness == 15
    assert reloaded.effect == "rainbow_wave"


def test_batch_update_persists_once(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config, file_storage

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    config = Config()
    real_merge = file_storage.merge_config_settings_atomic
    merge_calls: list[dict[str, object]] = []

    def counting_merge(**kwargs):
        merge_calls.append(dict(kwargs))
        return real_merge(**kwargs)

    monkeypatch.setattr(file_storage, "merge_config_settings_atomic", counting_merge)

    with config.batch_update():
        config.brightness = 21
        config.effect = "rainbow_wave"
        config.autostart = False

    reloaded = Config()
    assert len(merge_calls) == 1
    assert reloaded.brightness == 20
    assert reloaded.effect == "rainbow_wave"
    assert reloaded.autostart is False


def test_batch_update_rolls_back_when_persistence_fails(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config, ConfigPersistenceError, file_storage

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    config = Config()
    original_brightness = config.brightness
    original_effect = config.effect
    monkeypatch.setattr(file_storage, "merge_config_settings_atomic", lambda **_kwargs: None)

    with pytest.raises(ConfigPersistenceError, match="Could not persist"), config.batch_update():
        config.brightness = 3
        config.effect = "rainbow_wave"

    assert config.brightness == original_brightness
    assert config.effect == original_effect


def test_ordinary_setter_raises_and_rolls_back_when_persistence_fails(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config, ConfigPersistenceError, file_storage

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    config = Config()
    original_brightness = config.brightness
    original_effect = config.effect
    monkeypatch.setattr(file_storage, "merge_config_settings_atomic", lambda **_kwargs: None)

    with pytest.raises(ConfigPersistenceError, match="Could not persist configuration"):
        config.brightness = 3

    assert config.brightness == original_brightness
    assert config.effect == original_effect
    assert config._settings == config._persisted_settings


def test_apply_perkey_profile_state_raises_when_persistence_fails(tmp_path, monkeypatch) -> None:
    from keyrgb.core.config import Config, ConfigPersistenceError, file_storage

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    config = Config()
    original_colors = dict(config.per_key_colors)
    original_brightness = config.brightness
    monkeypatch.setattr(file_storage, "merge_config_settings_atomic", lambda **_kwargs: None)

    with pytest.raises(ConfigPersistenceError, match="Could not persist configuration"):
        config.apply_perkey_profile_state(
            {(0, 0): (1, 2, 3)},
            effect_brightness=40,
            perkey_brightness=40,
        )

    assert config.per_key_colors == original_colors
    assert config.brightness == original_brightness
