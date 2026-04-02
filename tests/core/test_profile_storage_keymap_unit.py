#!/usr/bin/env python3
"""Unit tests for profile keymap storage (core/profile/profiles.py)."""

from __future__ import annotations

import json

from src.core.resources.layouts import slot_id_for_key_id


class TestKeymapLoadSave:
    """Test load_keymap/save_keymap round-trips and edge cases."""

    def test_save_and_load_keymap_roundtrip(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """Save then load keymap should preserve data."""
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        keymap = {
            "ESC": ((0, 0),),
            "F1": ((0, 1),),
            "A": ((2, 0),),
            "SPACE": ((5, 6),),
        }

        profiles.save_keymap(keymap, "test_profile")
        loaded = profiles.load_keymap("test_profile")

        assert loaded == keymap

    def test_load_keymap_returns_default_if_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """If keymap.json doesn't exist, load_keymap should return default."""
        from src.core.profile import profiles
        from src.core.resources.defaults import DEFAULT_KEYMAP

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, keymap=temp_profile_dir / "nonexistent_keymap.json")

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        loaded = profiles.load_keymap("test_profile")
        expected = {}
        for key, value in DEFAULT_KEYMAP.items():
            row_text, col_text = value.split(",", 1)
            expected[str(slot_id_for_key_id("auto", key) or key)] = ((int(row_text), int(col_text)),)

        assert isinstance(loaded, dict)
        assert loaded == expected
        for key, val in loaded.items():
            assert isinstance(key, str)
            assert isinstance(val, tuple)
            assert val
            assert isinstance(val[0], tuple)
            assert len(val[0]) == 2

    def test_load_keymap_uses_layout_specific_default_if_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        from src.core.profile import profiles

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, keymap=temp_profile_dir / "nonexistent_keymap.json")

        monkeypatch.setattr(profiles, "paths_for", mock_paths)
        monkeypatch.setattr(profiles, "get_default_keymap", lambda layout_id=None: {"enter": "1,2", "layout": str(layout_id)})

        loaded = profiles.load_keymap("test_profile", physical_layout="jis")

        assert loaded == {str(slot_id_for_key_id("jis", "enter") or "enter"): ((1, 2),)}

    def test_load_keymap_skips_invalid_entries(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        """load_keymap should skip entries with wrong types or bad coords."""
        from src.core.profile import profiles

        keymap_file = temp_profile_dir / "keymap.json"
        keymap_file.write_text(
            json.dumps(
                {
                    "ESC": "0,0",  # valid
                    "F1": [0, 1],  # valid list format
                    "ENTER": ["1,2", [1, 3]],  # valid multi-cell format
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

        assert loaded == {"ESC": ((0, 0),), "F1": ((0, 1),), "ENTER": ((1, 2), (1, 3))}

    def test_save_keymap_persists_multi_cell_entries_as_lists(self, temp_profile_dir, profile_paths_factory, monkeypatch):
        from src.core.profile import profiles

        keymap_file = temp_profile_dir / "keymap.json"

        def mock_paths(_name):
            return profile_paths_factory(temp_profile_dir, keymap=keymap_file)

        monkeypatch.setattr(profiles, "paths_for", mock_paths)

        profiles.save_keymap({"enter": ((1, 2), (1, 3))}, "test_profile")

        saved = json.loads(keymap_file.read_text())

        assert saved == {str(slot_id_for_key_id("auto", "enter") or "enter"): ["1,2", "1,3"]}
