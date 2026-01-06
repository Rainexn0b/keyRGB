#!/usr/bin/env python3
"""Unit tests for profile global layout storage (core/profile/profiles.py)."""

from __future__ import annotations

import json


class TestLayoutGlobalLoadSave:
    """Test load_layout_global/save_layout_global."""

    def test_save_and_load_layout_global_roundtrip(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Save then load layout tweaks should preserve data."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        tweaks = {"dx": 1.5, "dy": -0.5, "sx": 1.1, "sy": 0.9, "inset": 0.08}

        profiles.save_layout_global(tweaks, "test_profile")
        loaded = profiles.load_layout_global("test_profile")

        assert loaded == tweaks

    def test_load_layout_global_clamps_inset(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """inset should be clamped to [0.0, 0.20]."""
        from src.core.profile import profiles

        layout_file = temp_profile_dir / "layout.json"
        layout_file.write_text(json.dumps({"dx": 0, "dy": 0, "sx": 1, "sy": 1, "inset": 0.99}))

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, layout_global=layout_file)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_layout_global("test_profile")
        assert loaded["inset"] == 0.20

    def test_load_layout_global_returns_default_if_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """If layout.json doesn't exist, return defaults."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, layout_global=temp_profile_dir / "nonexistent_layout.json")

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_layout_global("test_profile")
        assert loaded == {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
