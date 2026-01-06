#!/usr/bin/env python3
"""Unit tests for profile keymap storage (core/profile/profiles.py)."""

from __future__ import annotations

import json


class TestKeymapLoadSave:
    """Test load_keymap/save_keymap round-trips and edge cases."""

    def test_save_and_load_keymap_roundtrip(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Save then load keymap should preserve data."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir)

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

    def test_load_keymap_returns_default_if_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """If keymap.json doesn't exist, load_keymap should return default."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, keymap=temp_profile_dir / "nonexistent_keymap.json")

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_keymap("test_profile")

        assert isinstance(loaded, dict)
        assert len(loaded) > 0
        for key, val in loaded.items():
            assert isinstance(key, str)
            assert isinstance(val, tuple)
            assert len(val) == 2

    def test_load_keymap_skips_invalid_entries(self, temp_profile_dir, profile_paths_factory, monkeypatch):
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
                }
            )
        )

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, keymap=keymap_file)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_keymap("test_profile")

        assert loaded == {"ESC": (0, 0), "F1": (0, 1)}
