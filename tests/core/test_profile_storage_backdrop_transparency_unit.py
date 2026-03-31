#!/usr/bin/env python3
"""Unit tests for profile backdrop transparency storage (core/profile/profiles.py)."""

from __future__ import annotations


class TestBackdropTransparency:
    def test_defaults_to_zero_when_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch) -> None:
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(
                temp_profile_dir,
                backdrop_settings=temp_profile_dir / "missing_backdrop_settings.json",
            )

        monkeypatch.setattr(profiles, "paths_for", mock_paths)
        assert profiles.load_backdrop_transparency("test_profile") == 0

    def test_roundtrips_and_clamps(self, temp_profile_dir, profile_paths_factory, monkeypatch) -> None:
        from src.core.profile import profiles

        settings_file = temp_profile_dir / "backdrop_settings.json"

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, backdrop_settings=settings_file)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        profiles.save_backdrop_transparency(42, "test_profile")
        assert profiles.load_backdrop_transparency("test_profile") == 42

        profiles.save_backdrop_transparency(999, "test_profile")
        assert profiles.load_backdrop_transparency("test_profile") == 100

        profiles.save_backdrop_transparency(-10, "test_profile")
        assert profiles.load_backdrop_transparency("test_profile") == 0
