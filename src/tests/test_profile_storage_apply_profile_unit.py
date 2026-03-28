#!/usr/bin/env python3
"""Unit tests for applying profiles to config (core/profile/profiles.py)."""

from __future__ import annotations


class TestApplyProfileToConfig:
    """Test apply_profile_to_config logic."""

    def test_apply_profile_sets_effect_and_colors(self):
        """apply_profile_to_config should set effect='perkey' and per_key_colors."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg.brightness = 75

        colors = {(0, 0): (255, 0, 0), (1, 1): (0, 255, 0)}

        apply_profile_to_config(cfg, colors)

        assert cfg.effect == "perkey"
        assert cfg.per_key_colors == colors

    def test_apply_profile_bumps_brightness_if_zero(self):
        """If brightness is 0, apply_profile_to_config should set it to 50."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg.brightness = 0

        apply_profile_to_config(cfg, {})

        assert cfg.brightness == 50
        assert cfg.effect == "perkey"

    def test_apply_dim_profile_sets_global_and_perkey_brightness(self, monkeypatch):
        """The built-in dim profile must set the steady-state global brightness too.

        Reactive effects use cfg.brightness as the baseline hardware level, so
        dim cannot be represented by perkey_brightness alone.
        """
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "dim")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 25
        cfg.brightness = 25
        cfg.perkey_brightness = 25

        apply_profile_to_config(cfg, {})

        assert cfg.effect_brightness == 10
        assert cfg.brightness == 10
        assert cfg.perkey_brightness == 10
        assert cfg.effect == "perkey"

    def test_apply_light_profile_restores_built_in_baseline_brightness(self, monkeypatch):
        """The built-in light profile should restore the normal full baseline."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "light")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 15
        cfg.brightness = 15
        cfg.perkey_brightness = 15

        apply_profile_to_config(cfg, {})

        assert cfg.effect_brightness == 50
        assert cfg.brightness == 50
        assert cfg.perkey_brightness == 50
        assert cfg.effect == "perkey"

    def test_migrate_builtin_dim_profile_repairs_stale_global_brightness(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "dim")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 25
        cfg.brightness = 15
        cfg.perkey_brightness = 15

        changed = migrate_builtin_profile_brightness(cfg)

        assert changed is True
        assert cfg.effect_brightness == 10
        assert cfg.brightness == 10
        assert cfg.perkey_brightness == 10

    def test_migrate_builtin_light_profile_repairs_stale_dim_level(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "light")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 10
        cfg.brightness = 10
        cfg.perkey_brightness = 10

        changed = migrate_builtin_profile_brightness(cfg)

        assert changed is True
        assert cfg.effect_brightness == 50
        assert cfg.brightness == 50
        assert cfg.perkey_brightness == 50
