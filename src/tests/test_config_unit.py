#!/usr/bin/env python3
"""Unit tests for core/config.py.

Focuses on small behaviors that should not depend on real user config.
"""

from __future__ import annotations


def test_return_effect_after_effect_sanitizes_invalid_values(tmp_path, monkeypatch) -> None:
    from src.core.config import Config

    # Avoid touching the user's real config.
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))

    cfg = Config()

    # Simulate a broken/unknown persisted value.
    cfg._settings["return_effect_after_effect"] = "totally-not-a-mode"
    assert cfg.return_effect_after_effect is None

    # Known values should pass through, normalized.
    cfg._settings["return_effect_after_effect"] = "PERKEY"
    assert cfg.return_effect_after_effect == "perkey"

    cfg._settings["return_effect_after_effect"] = "perkey_pulse"
    assert cfg.return_effect_after_effect == "perkey"
