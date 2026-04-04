#!/usr/bin/env python3
"""Unit tests for profile backdrop transparency storage (core/profile/profiles.py)."""

from __future__ import annotations

import pytest

from src.core.profile import _backdrop as backdrop_ops
from src.core.profile import profiles


class _BrokenInt:
    def __int__(self) -> int:
        raise RuntimeError("broken __int__")


def _patch_backdrop_paths(
    monkeypatch, temp_profile_dir, profile_paths_factory, filename: str = "backdrop_settings.json"
):
    paths = profile_paths_factory(
        temp_profile_dir,
        backdrop_settings=temp_profile_dir / filename,
    )
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)
    monkeypatch.setattr(backdrop_ops, "paths_for", lambda _name=None: paths)
    return paths


class TestBackdropTransparency:
    def test_defaults_to_zero_when_missing(self, temp_profile_dir, profile_paths_factory, monkeypatch) -> None:
        _patch_backdrop_paths(
            monkeypatch,
            temp_profile_dir,
            profile_paths_factory,
            filename="missing_backdrop_settings.json",
        )

        assert profiles.load_backdrop_transparency("test_profile") == 0

    def test_roundtrips_and_clamps(self, temp_profile_dir, profile_paths_factory, monkeypatch) -> None:
        _patch_backdrop_paths(monkeypatch, temp_profile_dir, profile_paths_factory)

        profiles.save_backdrop_transparency(42, "test_profile")
        assert profiles.load_backdrop_transparency("test_profile") == 42

        profiles.save_backdrop_transparency(999, "test_profile")
        assert profiles.load_backdrop_transparency("test_profile") == 100

        profiles.save_backdrop_transparency(-10, "test_profile")
        assert profiles.load_backdrop_transparency("test_profile") == 0

    @pytest.mark.parametrize("raw_value", ["bad", None, {}, []])
    def test_load_falls_back_to_zero_for_invalid_persisted_values(
        self,
        raw_value,
        temp_profile_dir,
        profile_paths_factory,
        monkeypatch,
    ) -> None:
        paths = _patch_backdrop_paths(monkeypatch, temp_profile_dir, profile_paths_factory)
        profiles.write_json_atomic(paths.backdrop_settings, {"transparency": raw_value})

        assert profiles.load_backdrop_transparency("test_profile") == 0

    def test_load_propagates_unexpected_int_bugs(self, monkeypatch) -> None:
        monkeypatch.setattr(
            backdrop_ops,
            "_load_backdrop_settings",
            lambda _name=None: {"transparency": _BrokenInt()},
        )

        with pytest.raises(RuntimeError, match="broken __int__"):
            profiles.load_backdrop_transparency("test_profile")

    @pytest.mark.parametrize("raw_value", ["bad", None, object()])
    def test_save_falls_back_to_zero_for_invalid_input(
        self,
        raw_value,
        temp_profile_dir,
        profile_paths_factory,
        monkeypatch,
    ) -> None:
        _patch_backdrop_paths(monkeypatch, temp_profile_dir, profile_paths_factory)

        profiles.save_backdrop_transparency(raw_value, "test_profile")

        assert profiles.load_backdrop_transparency("test_profile") == 0

    def test_save_propagates_unexpected_int_bugs(self, temp_profile_dir, profile_paths_factory, monkeypatch) -> None:
        _patch_backdrop_paths(monkeypatch, temp_profile_dir, profile_paths_factory)

        with pytest.raises(RuntimeError, match="broken __int__"):
            profiles.save_backdrop_transparency(_BrokenInt(), "test_profile")

    def test_backdrop_mode_defaults_to_builtin_when_missing(
        self, temp_profile_dir, profile_paths_factory, monkeypatch
    ) -> None:
        _patch_backdrop_paths(
            monkeypatch,
            temp_profile_dir,
            profile_paths_factory,
            filename="missing_backdrop_settings.json",
        )

        assert profiles.load_backdrop_mode("test_profile") == "builtin"

    def test_backdrop_mode_roundtrips_and_preserves_transparency(
        self, temp_profile_dir, profile_paths_factory, monkeypatch
    ) -> None:
        _patch_backdrop_paths(monkeypatch, temp_profile_dir, profile_paths_factory)

        profiles.save_backdrop_transparency(42, "test_profile")
        profiles.save_backdrop_mode("none", "test_profile")

        assert profiles.load_backdrop_mode("test_profile") == "none"
        assert profiles.load_backdrop_transparency("test_profile") == 42
