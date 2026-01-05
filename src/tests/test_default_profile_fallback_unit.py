from __future__ import annotations


def test_get_active_profile_falls_back_to_default_profile(tmp_path, monkeypatch):
    """If active_profile.json is missing, KeyRGB should fall back to the user-set default profile."""

    from src.core.config import Config
    from src.core.profile import paths

    monkeypatch.setattr(Config, "CONFIG_DIR", tmp_path / "config", raising=False)

    # No active profile set yet.
    assert not paths.active_profile_path().exists()

    # Set default profile to dark.
    paths.set_default_profile("dark")

    assert paths.get_active_profile() == "dark"
