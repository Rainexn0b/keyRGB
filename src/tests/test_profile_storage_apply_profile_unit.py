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
