#!/usr/bin/env python3
"""Unit tests for applying profiles to config (core/profile/profiles.py)."""

from __future__ import annotations

import pytest


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

    def test_apply_dim_profile_sets_global_and_perkey_brightness(self, monkeypatch):
        """The built-in dim profile must set the steady-state global brightness too.

        Reactive effects use cfg.brightness as the baseline hardware level, so
        dim cannot be represented by perkey_brightness alone.
        """
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "dim")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 25
        cfg.brightness = 25
        cfg.perkey_brightness = 25

        apply_profile_to_config(cfg, {})

        assert cfg.effect_brightness == 5
        assert cfg.brightness == 5
        assert cfg.perkey_brightness == 5
        assert cfg.effect == "perkey"

    def test_apply_light_profile_restores_built_in_baseline_brightness(self, monkeypatch):
        """The built-in light profile should restore the normal full baseline."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "light")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 15
        cfg.brightness = 15
        cfg.perkey_brightness = 15

        apply_profile_to_config(cfg, {})

        assert cfg.effect_brightness == 50
        assert cfg.brightness == 50
        assert cfg.perkey_brightness == 50
        assert cfg.effect == "perkey"

    def test_migrate_builtin_dim_profile_repairs_stale_global_brightness(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "dim")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 25
        cfg.brightness = 15
        cfg.perkey_brightness = 15

        changed = migrate_builtin_profile_brightness(cfg)

        assert changed is True
        assert cfg.effect_brightness == 5
        assert cfg.brightness == 5
        assert cfg.perkey_brightness == 5

    def test_migrate_builtin_dim_profile_from_previous_10_target(self, monkeypatch):
        """Users previously at the old dim target (10) must also be migrated to the new 5."""
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "dim")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 25
        cfg.brightness = 10
        cfg.perkey_brightness = 10

        changed = migrate_builtin_profile_brightness(cfg)

        assert changed is True
        assert cfg.effect_brightness == 5
        assert cfg.brightness == 5
        assert cfg.perkey_brightness == 5

    def test_migrate_builtin_dim_profile_no_op_when_already_at_5(self, monkeypatch):
        """Users already at the current dim target must not be migrated."""
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "dim")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 5
        cfg.brightness = 5
        cfg.perkey_brightness = 5

        changed = migrate_builtin_profile_brightness(cfg)

        assert changed is False

    def test_migrate_builtin_light_profile_repairs_stale_dim_level(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "light")

        cfg = Config()
        cfg.effect = "perkey"
        cfg.effect_brightness = 10
        cfg.brightness = 10
        cfg.perkey_brightness = 10

        changed = migrate_builtin_profile_brightness(cfg)

        assert changed is True
        assert cfg.effect_brightness == 50
        assert cfg.brightness == 50
        assert cfg.perkey_brightness == 50

    def test_migrate_builtin_profile_logs_active_profile_lookup_failure(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile import profiles

        logs: list[tuple[str, str, BaseException | None]] = []

        def fail_active_profile():
            raise RuntimeError("boom")

        def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
            logs.append((key, msg, exc))
            return True

        monkeypatch.setattr(profiles, "get_active_profile", fail_active_profile)
        monkeypatch.setattr(profiles, "log_throttled", fake_log_throttled)

        changed = profiles.migrate_builtin_profile_brightness(Config())

        assert changed is False
        assert len(logs) == 1
        assert logs[0][0] == "profiles.migrate_builtin_profile_brightness.active_profile"
        assert logs[0][1] == "Failed to resolve active profile during built-in brightness migration"
        assert isinstance(logs[0][2], RuntimeError)

    def test_migrate_builtin_profile_propagates_unexpected_active_profile_lookup_failure(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile import profiles

        monkeypatch.setattr(profiles, "get_active_profile", lambda: (_ for _ in ()).throw(AssertionError("boom")))

        with pytest.raises(AssertionError, match="boom"):
            profiles.migrate_builtin_profile_brightness(Config())

    def test_apply_dim_profile_logs_brightness_set_failure_and_continues(self, monkeypatch):
        from src.core.profile import profiles

        logs: list[tuple[str, str, BaseException | None]] = []

        class ConfigStub:
            def __init__(self) -> None:
                self._effect_brightness = 25
                self.brightness = 25
                self.perkey_brightness = 25
                self.effect = "wave"
                self.per_key_colors = {}

            @property
            def effect_brightness(self) -> int:
                return self._effect_brightness

            @effect_brightness.setter
            def effect_brightness(self, _value: int) -> None:
                raise RuntimeError("deny")

        def fake_log_throttled(_logger, key, *, interval_s, level, msg, exc=None):
            logs.append((key, msg, exc))
            return True

        monkeypatch.setattr(profiles, "get_active_profile", lambda: "dim")
        monkeypatch.setattr(profiles, "log_throttled", fake_log_throttled)

        cfg = ConfigStub()
        colors = {(0, 0): (1, 2, 3)}

        profiles.apply_profile_to_config(cfg, colors)

        assert cfg.effect == "perkey"
        assert cfg.per_key_colors == colors
        assert cfg.effect_brightness == 25
        assert cfg.brightness == 25
        assert cfg.perkey_brightness == 5
        assert len(logs) == 1
        assert logs[0][0] == "profiles.apply_profile_to_config.set_effect_brightness"
        assert logs[0][1] == "Failed to set effect brightness while applying a profile"
        assert isinstance(logs[0][2], RuntimeError)

    def test_apply_profile_propagates_unexpected_brightness_getter_failure(self, monkeypatch):
        from src.core.profile import profiles

        class ConfigStub:
            def __init__(self) -> None:
                self.brightness = 25
                self.perkey_brightness = 25
                self.effect = "wave"
                self.per_key_colors = {}

            @property
            def effect_brightness(self) -> int:
                raise AssertionError("unexpected getter bug")

        monkeypatch.setattr(profiles, "get_active_profile", lambda: "dim")

        with pytest.raises(AssertionError, match="unexpected getter bug"):
            profiles.apply_profile_to_config(ConfigStub(), {(0, 0): (1, 2, 3)})

    def test_apply_profile_propagates_unexpected_brightness_setter_failure(self, monkeypatch):
        from src.core.profile import profiles

        class ConfigStub:
            def __init__(self) -> None:
                self._effect_brightness = 25
                self.brightness = 25
                self.perkey_brightness = 25
                self.effect = "wave"
                self.per_key_colors = {}

            @property
            def effect_brightness(self) -> int:
                return self._effect_brightness

            @effect_brightness.setter
            def effect_brightness(self, _value: int) -> None:
                raise AssertionError("unexpected setter bug")

        monkeypatch.setattr(profiles, "get_active_profile", lambda: "dim")

        with pytest.raises(AssertionError, match="unexpected setter bug"):
            profiles.apply_profile_to_config(ConfigStub(), {(0, 0): (1, 2, 3)})
