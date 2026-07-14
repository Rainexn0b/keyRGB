#!/usr/bin/env python3
"""Unit tests for applying profiles to config (core/profile/profiles.py)."""

from __future__ import annotations

from copy import deepcopy

import pytest


class TestApplyProfileToConfig:
    """Test apply_profile_to_config logic."""

    def test_apply_profile_preserves_selected_effect_and_sets_colors(self):
        """apply_profile_to_config should update the base map without forcing the selected effect."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg.effect = "rainbow"
        cfg.brightness = 75

        colors = {(0, 0): (255, 0, 0), (1, 1): (0, 255, 0)}

        apply_profile_to_config(cfg, colors)

        assert cfg.effect == "rainbow"
        assert cfg.per_key_colors == colors

    def test_apply_profile_bumps_brightness_if_zero(self):
        """If brightness is 0, apply_profile_to_config should set it to 50."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg.effect = "none"
        cfg.brightness = 0

        apply_profile_to_config(cfg, {})

        assert cfg.brightness == 50
        assert cfg.effect == "none"

    def test_apply_profile_persists_single_complete_config_snapshot(self, monkeypatch):
        """Profile switches should not expose intermediate config states to pollers."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg._settings["effect"] = "none"
        cfg._settings["brightness"] = 25
        cfg._settings["perkey_brightness"] = 25
        cfg._settings["per_key_colors"] = {"0,0": [255, 0, 0]}

        snapshots: list[dict] = []
        monkeypatch.setattr(cfg, "_save", lambda: snapshots.append(deepcopy(cfg._settings)))

        colors = {(0, 0): (0, 0, 255), (0, 1): (0, 0, 255)}

        apply_profile_to_config(cfg, colors)

        assert len(snapshots) == 1
        assert snapshots[0]["effect"] == "none"
        assert snapshots[0]["per_key_colors"] == {"0,0": [0, 0, 255], "0,1": [0, 0, 255]}
        assert cfg.effect == "none"
        assert cfg.per_key_colors == colors

    def test_apply_profile_persists_secondary_state_in_same_snapshot(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg._settings["effect"] = "none"
        cfg._settings["brightness"] = 25
        cfg._settings["perkey_brightness"] = 25
        cfg._settings["secondary_device_state"] = {
            "logo": {"brightness": 35, "legacy": "preserve"},
        }

        snapshots: list[dict] = []
        monkeypatch.setattr(cfg, "_save", lambda: snapshots.append(deepcopy(cfg._settings)))

        apply_profile_to_config(
            cfg,
            {(0, 0): (0, 0, 255)},
            secondary_lighting={
                "version": 1,
                "areas": {
                    "logo": {"enabled": False, "color": [300, -1, 7], "future": True},
                    "neon": {"enabled": True, "color": [1, 2, 3]},
                },
            },
        )

        assert len(snapshots) == 1
        assert snapshots[0]["per_key_colors"] == {"0,0": [0, 0, 255]}
        assert snapshots[0]["secondary_device_state"] == {
            "logo": {"brightness": 35, "legacy": "preserve", "enabled": False, "color": [255, 0, 7], "future": True},
            "neon": {"enabled": True, "color": [1, 2, 3]},
            "lightbar": {"enabled": False},
            "mouse": {"enabled": False},
            "ite8258_chassis_logo": {"enabled": False},
            "ite8258_chassis_neon": {"enabled": False},
            "ite8258_chassis_vent": {"enabled": False},
        }

    def test_explicit_empty_secondary_profile_disables_known_routes_and_preserves_unknown_state(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg._settings["secondary_device_state"] = {
            "lightbar": {"enabled": True, "brightness": 35, "color": [1, 2, 3]},
            "ite8258_chassis_logo": {"enabled": True, "color": [4, 5, 6]},
            "future_route": {"enabled": True, "future": "preserve"},
        }
        monkeypatch.setattr(cfg, "_save", lambda: None)

        apply_profile_to_config(
            cfg,
            {},
            secondary_lighting={"version": 1, "areas": {}},
        )

        state = cfg._settings["secondary_device_state"]
        assert state["lightbar"] == {
            "enabled": False,
            "brightness": 35,
            "color": [1, 2, 3],
        }
        assert state["ite8258_chassis_logo"] == {
            "enabled": False,
            "color": [4, 5, 6],
        }
        assert state["future_route"] == {"enabled": True, "future": "preserve"}

    def test_partial_secondary_profile_disables_only_omitted_known_routes(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        cfg = Config()
        cfg._settings["secondary_device_state"] = {
            "lightbar": {"enabled": True, "brightness": 25},
            "mouse": {"enabled": True, "brightness": 20},
        }
        monkeypatch.setattr(cfg, "_save", lambda: None)

        apply_profile_to_config(
            cfg,
            {},
            secondary_lighting={
                "version": 1,
                "areas": {"lightbar": {"enabled": True, "brightness": 40}},
            },
        )

        state = cfg._settings["secondary_device_state"]
        assert state["lightbar"] == {"enabled": True, "brightness": 40}
        assert state["mouse"] == {"enabled": False, "brightness": 20}

    def test_apply_light_profile_restores_built_in_baseline_brightness(self, monkeypatch):
        """The built-in light profile should restore the normal full baseline."""
        from src.core.config import Config
        from src.core.profile.profiles import apply_profile_to_config

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "default")

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

    def test_migrate_builtin_light_profile_repairs_stale_dim_level(self, monkeypatch):
        from src.core.config import Config
        from src.core.profile.profiles import migrate_builtin_profile_brightness

        monkeypatch.setattr("src.core.profile.profiles.get_active_profile", lambda: "default")

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

    def test_apply_light_profile_logs_brightness_set_failure_and_continues(self, monkeypatch):
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

        monkeypatch.setattr(profiles, "get_active_profile", lambda: "default")
        monkeypatch.setattr(profiles, "log_throttled", fake_log_throttled)

        cfg = ConfigStub()
        colors = {(0, 0): (1, 2, 3)}

        profiles.apply_profile_to_config(cfg, colors)

        assert cfg.effect == "wave"
        assert cfg.per_key_colors == colors
        assert cfg.effect_brightness == 25
        assert cfg.brightness == 25
        assert cfg.perkey_brightness == 50
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

        monkeypatch.setattr(profiles, "get_active_profile", lambda: "default")

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

        monkeypatch.setattr(profiles, "get_active_profile", lambda: "default")

        with pytest.raises(AssertionError, match="unexpected setter bug"):
            profiles.apply_profile_to_config(ConfigStub(), {(0, 0): (1, 2, 3)})
