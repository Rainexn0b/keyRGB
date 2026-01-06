#!/usr/bin/env python3
"""Unit tests for profile per-key layout storage (core/profile/profiles.py)."""

from __future__ import annotations

import json


class TestLayoutPerKeyLoadSave:
    """Test load_layout_per_key/save_layout_per_key."""

    def test_save_and_load_per_key_tweaks_roundtrip(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Save then load per-key tweaks should preserve data."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        per_key = {
            "ESC": {"dx": 0.5, "dy": -0.2, "inset": 0.10},
            "SPACE": {"sx": 1.2, "sy": 0.8},
        }

        profiles.save_layout_per_key(per_key, "test_profile")
        loaded = profiles.load_layout_per_key("test_profile")

        assert loaded == per_key

    def test_load_per_key_clamps_inset_per_key(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Per-key inset should be clamped to [0.0, 0.20]."""
        from src.core.profile import profiles

        layout_file = temp_profile_dir / "layout_per_key.json"
        layout_file.write_text(json.dumps({"KEY1": {"inset": 0.50}}))

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, layout_per_key=layout_file)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_layout_per_key("test_profile")
        assert loaded["KEY1"]["inset"] == 0.20
