#!/usr/bin/env python3
"""Unit tests for profile storage (core/profile/profiles.py).

Tests JSON load/save round-trips, malformed data handling, and validation/clamping logic.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_profile_dir(tmp_path):
    """Create a temporary profile directory structure."""
    profile_dir = tmp_path / "profiles" / "test_profile"
    profile_dir.mkdir(parents=True)
    return profile_dir


class TestKeymapLoadSave:
    """Test load_keymap/save_keymap round-trips and edge cases."""

    def test_save_and_load_keymap_roundtrip(self, temp_profile_dir, monkeypatch):
        """Save then load keymap should preserve data."""
        from src.core.profile import profiles

        # Mock paths_for to return our temp dir
        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        keymap = {
            "ESC": (0, 0),
            "F1": (0, 1),
            "A": (2, 0),
            "SPACE": (5, 6),
        }

        profiles.save_keymap(keymap, "test_profile")
        loaded = profiles.load_keymap("test_profile")

        assert loaded == keymap

    def test_load_keymap_returns_default_if_missing(self, temp_profile_dir, monkeypatch):
        """If keymap.json doesn't exist, load_keymap should return default."""
        from src.core.profile import profiles

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "nonexistent_keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_keymap("test_profile")
        # Should return the DEFAULT_KEYMAP (which has tuples as values)
        from src.core.resources.defaults import DEFAULT_KEYMAP

        # DEFAULT_KEYMAP values are tuples, not strings
        assert isinstance(loaded, dict)
        assert len(loaded) > 0
        # Just verify structure, not exact default (which may change)
        for key, val in loaded.items():
            assert isinstance(key, str)
            assert isinstance(val, tuple)
            assert len(val) == 2

    def test_load_keymap_skips_invalid_entries(self, temp_profile_dir, monkeypatch):
        """load_keymap should skip entries with wrong types or bad coords."""
        from src.core.profile import profiles

        keymap_file = temp_profile_dir / "keymap.json"
        keymap_file.write_text(
            json.dumps(
                {
                    "ESC": "0,0",  # valid
                    "F1": [0, 1],  # valid list format
                    "BAD1": "not,a,coord",  # too many commas
                    "BAD2": "nope",  # non-numeric
                    "BAD3": [1],  # wrong list length
                    # Don't include non-string keys as they won't survive JSON round-trip
                }
            )
        )

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=keymap_file,
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_keymap("test_profile")

        # Should only have the valid entries
        assert loaded == {"ESC": (0, 0), "F1": (0, 1)}


class TestLayoutGlobalLoadSave:
    """Test load_layout_global/save_layout_global."""

    def test_save_and_load_layout_global_roundtrip(self, temp_profile_dir, monkeypatch):
        """Save then load layout tweaks should preserve data."""
        from src.core.profile import profiles

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        tweaks = {"dx": 1.5, "dy": -0.5, "sx": 1.1, "sy": 0.9, "inset": 0.08}

        profiles.save_layout_global(tweaks, "test_profile")
        loaded = profiles.load_layout_global("test_profile")

        assert loaded == tweaks

    def test_load_layout_global_clamps_inset(self, temp_profile_dir, monkeypatch):
        """inset should be clamped to [0.0, 0.20]."""
        from src.core.profile import profiles

        layout_file = temp_profile_dir / "layout.json"
        layout_file.write_text(json.dumps({"dx": 0, "dy": 0, "sx": 1, "sy": 1, "inset": 0.99}))

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=layout_file,
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_layout_global("test_profile")
        # inset should be clamped to max 0.20
        assert loaded["inset"] == 0.20

    def test_load_layout_global_returns_default_if_missing(self, temp_profile_dir, monkeypatch):
        """If layout.json doesn't exist, return defaults."""
        from src.core.profile import profiles

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "nonexistent_layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_layout_global("test_profile")
        assert loaded == {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}


class TestLayoutPerKeyLoadSave:
    """Test load_layout_per_key/save_layout_per_key."""

    def test_save_and_load_per_key_tweaks_roundtrip(self, temp_profile_dir, monkeypatch):
        """Save then load per-key tweaks should preserve data."""
        from src.core.profile import profiles

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        per_key = {
            "ESC": {"dx": 0.5, "dy": -0.2, "inset": 0.10},
            "SPACE": {"sx": 1.2, "sy": 0.8},
        }

        profiles.save_layout_per_key(per_key, "test_profile")
        loaded = profiles.load_layout_per_key("test_profile")

        assert loaded == per_key

    def test_load_per_key_clamps_inset_per_key(self, temp_profile_dir, monkeypatch):
        """Per-key inset should be clamped to [0.0, 0.20]."""
        from src.core.profile import profiles

        layout_file = temp_profile_dir / "layout_per_key.json"
        layout_file.write_text(json.dumps({"KEY1": {"inset": 0.50}}))

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=layout_file,
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_layout_per_key("test_profile")
        assert loaded["KEY1"]["inset"] == 0.20


class TestPerKeyColorsLoadSave:
    """Test load_per_key_colors/save_per_key_colors."""

    def test_save_and_load_colors_roundtrip(self, temp_profile_dir, monkeypatch):
        """Save then load per-key colors should preserve data."""
        from src.core.profile import profiles

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        colors = {
            (0, 0): (255, 0, 0),
            (0, 1): (0, 255, 0),
            (5, 6): (0, 0, 255),
        }

        profiles.save_per_key_colors(colors, "test_profile")
        loaded = profiles.load_per_key_colors("test_profile")

        assert loaded == colors

    def test_load_colors_returns_default_if_missing(self, temp_profile_dir, monkeypatch):
        """If colors.json doesn't exist, return DEFAULT_COLORS."""
        from src.core.profile import profiles

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=temp_profile_dir / "nonexistent_colors.json",
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_per_key_colors("test_profile")

        from src.core.resources.defaults import DEFAULT_COLORS

        assert loaded == DEFAULT_COLORS

    def test_load_colors_skips_invalid_entries(self, temp_profile_dir, monkeypatch):
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

        def mock_paths(name):
            from src.core.profile.paths import ProfilePaths

            return ProfilePaths(
                root=temp_profile_dir,
                keymap=temp_profile_dir / "keymap.json",
                layout_global=temp_profile_dir / "layout.json",
                layout_per_key=temp_profile_dir / "layout_per_key.json",
                per_key_colors=colors_file,
                backdrop_image=temp_profile_dir / "backdrop.png",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_per_key_colors("test_profile")

        # Should only have the valid entries
        assert loaded == {
            (0, 0): (255, 0, 0),
            (1, 2): (0, 255, 0),
        }


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
