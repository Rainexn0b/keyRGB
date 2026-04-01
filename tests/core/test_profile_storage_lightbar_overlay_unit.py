from __future__ import annotations

from src.core.profile import profiles


class TestProfileStorageLightbarOverlayUnit:
    def test_save_and_load_lightbar_overlay_roundtrip(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        monkeypatch.setattr(
            profiles,
            "paths_for",
            lambda _name=None: profile_paths_factory(temp_profile_dir),
        )

        payload = {
            "visible": False,
            "length": 0.84,
            "thickness": 0.18,
            "dx": 0.12,
            "dy": -0.08,
            "inset": 0.03,
        }

        profiles.save_lightbar_overlay(payload, "test_profile")
        loaded = profiles.load_lightbar_overlay("test_profile")

        assert loaded == payload

    def test_load_lightbar_overlay_clamps_out_of_range_values(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        paths = profile_paths_factory(temp_profile_dir)
        monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)

        profiles.write_json_atomic(
            paths.lightbar_overlay,
            {
                "visible": 0,
                "length": 9.0,
                "thickness": -1.0,
                "dx": 4.0,
                "dy": -4.0,
                "inset": 1.0,
            },
        )

        loaded = profiles.load_lightbar_overlay("test_profile")

        assert loaded == {
            "visible": False,
            "length": 1.0,
            "thickness": 0.04,
            "dx": 0.5,
            "dy": -0.5,
            "inset": 0.25,
        }

    def test_load_lightbar_overlay_returns_default_if_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        monkeypatch.setattr(
            profiles,
            "paths_for",
            lambda _name=None: profile_paths_factory(temp_profile_dir),
        )

        loaded = profiles.load_lightbar_overlay("test_profile")

        assert loaded == {
            "visible": True,
            "length": 0.72,
            "thickness": 0.12,
            "dx": 0.0,
            "dy": 0.0,
            "inset": 0.04,
        }