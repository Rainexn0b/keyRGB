#!/usr/bin/env python3
"""Unit tests for decoupled effect vs per-key brightness.

Historically, KeyRGB stored a single "brightness" setting. That meant changing
brightness in per-key mode overwrote the brightness used for effects (and vice
versa). We now persist a dedicated "perkey_brightness" so the two modes can be
set independently and survive restarts.
"""

from __future__ import annotations

import json


def test_brightness_is_decoupled_by_mode(tmp_path, monkeypatch) -> None:
    from src.core.config import Config

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))

    cfg = Config()

    # Set an effect brightness.
    cfg.effect = "rainbow"
    cfg.brightness = 40
    assert cfg.effect_brightness == 40

    # Switching to per-key and changing brightness must not overwrite the
    # effect brightness.
    cfg.effect = "perkey"
    cfg.brightness = 10
    assert cfg.perkey_brightness == 10
    assert cfg.effect_brightness == 40

    # Switching back restores the effect brightness.
    cfg.effect = "rainbow"
    assert cfg.brightness == 40

    # And changing effect brightness must not overwrite per-key brightness.
    cfg.brightness = 25
    assert cfg.effect_brightness == 25
    assert cfg.perkey_brightness == 10


def test_old_config_migrates_perkey_brightness(tmp_path, monkeypatch) -> None:
    """Older config.json files had only "brightness".

    We migrate perkey_brightness from brightness on first load.
    """

    from src.core.config import Config

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"

    # Use a non-snapped value to ensure normalization occurs.
    cfg_path.write_text(json.dumps({"effect": "perkey", "brightness": 33}), encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(cfg_path))

    cfg = Config()

    # 33 should normalize to 35, and perkey_brightness should exist.
    assert cfg.effect == "perkey"
    assert cfg.perkey_brightness == 35
    assert cfg.effect_brightness == 35
    assert cfg.brightness == 35
