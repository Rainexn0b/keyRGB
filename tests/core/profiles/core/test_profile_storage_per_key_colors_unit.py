#!/usr/bin/env python3
"""Unit tests for profile per-key color storage (core/profile/profiles.py)."""

from __future__ import annotations

import json


class TestPerKeyColorsLoadSave:
    """Test load_per_key_colors/save_per_key_colors."""

    def test_save_and_load_colors_roundtrip(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Save then load per-key colors should preserve data."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        colors = {
            (0, 0): (255, 0, 0),
            (0, 1): (0, 255, 0),
            (5, 6): (0, 0, 255),
        }

        profiles.save_per_key_colors(colors, "test_profile")
        loaded = profiles.load_per_key_colors("test_profile")

        assert loaded == colors

    def test_load_colors_returns_default_if_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """If colors.json doesn't exist, return DEFAULT_COLORS."""
        from src.core.profile import profiles
        from src.core.resources.defaults import DEFAULT_COLORS

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, per_key_colors=temp_profile_dir / "nonexistent_colors.json")

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_per_key_colors("test_profile")

        assert loaded == DEFAULT_COLORS

    def test_load_colors_dark_profile_defaults_to_black(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Built-in 'dark' profile should default to all keys off/black."""
        from src.core.profile import profiles
        from src.core.resources.defaults import DEFAULT_COLORS

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, per_key_colors=temp_profile_dir / "nonexistent_colors.json")

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_per_key_colors("dark")

        assert loaded == {k: (0, 0, 0) for k in DEFAULT_COLORS.keys()}

    def test_load_colors_skips_invalid_entries(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """load_per_key_colors should skip entries with bad coords or RGB values."""
        from src.core.profile import profiles

        colors_file = temp_profile_dir / "colors.json"
        colors_file.write_text(
            json.dumps(
                {
                    "0,0": [255, 0, 0],  # valid
                    "1,2": [0, 255, 0],  # valid
                    "bad": [100, 100, 100],  # bad coord format
                    "3,4": [255, 255],  # wrong RGB length
                    "5,6": "not_rgb",  # not a list
                }
            )
        )

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, per_key_colors=colors_file)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_per_key_colors("test_profile")

        assert loaded == {
            (0, 0): (255, 0, 0),
            (1, 2): (0, 255, 0),
        }
