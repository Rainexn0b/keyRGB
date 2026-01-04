#!/usr/bin/env python3
"""Unit tests for tray/controllers/effect_selection.py - effect selection logic.

Tests the decision logic for applying effect selections without dependencies on
specific UI elements or hardware implementations.
"""

from __future__ import annotations

from unittest.mock import MagicMock


class TestEnsureConfigPerKeyColorsLoaded:
    """Test _ensure_config_per_key_colors_loaded helper."""

    def test_does_nothing_if_colors_already_loaded(self):
        """Should not load from profile if colors already exist."""
        from src.tray.controllers.effect_selection import _ensure_config_per_key_colors_loaded

        mock_config = MagicMock()
        mock_config.per_key_colors = {(0, 0): (255, 0, 0)}

        _ensure_config_per_key_colors_loaded(mock_config)

        # Should not change existing colors
        assert mock_config.per_key_colors == {(0, 0): (255, 0, 0)}

    def test_loads_from_active_profile_if_colors_empty(self, monkeypatch):
        """Should load from active profile when per_key_colors is empty."""
        from src.tray.controllers.effect_selection import _ensure_config_per_key_colors_loaded

        mock_config = MagicMock()
        mock_config.per_key_colors = {}

        # Mock the profiles module
        mock_profiles = MagicMock()
        mock_profiles.get_active_profile.return_value = "test_profile"
        mock_profiles.load_per_key_colors.return_value = {(0, 0): (0, 255, 0)}

        with monkeypatch.context() as m:
            m.setattr("src.tray.controllers.effect_selection.profiles", mock_profiles, raising=False)
            _ensure_config_per_key_colors_loaded(mock_config)

        assert mock_config.per_key_colors == {(0, 0): (0, 255, 0)}

    def test_handles_import_error_gracefully(self, monkeypatch):
        """Should not crash if profiles module import fails."""
        from src.tray.controllers.effect_selection import _ensure_config_per_key_colors_loaded

        mock_config = MagicMock()
        mock_config.per_key_colors = {}

        # Simulate import failure
        def fake_import(name, *args, **kwargs):
            if "profiles" in name:
                raise ImportError("Module not found")
            return __import__(name, *args, **kwargs)

        with monkeypatch.context() as m:
            m.setattr("builtins.__import__", fake_import)
            # Should not raise
            _ensure_config_per_key_colors_loaded(mock_config)


class TestApplyEffectSelection:
    """Test apply_effect_selection decision logic."""

    def test_none_effect_stops_engine_and_sets_static_color(self):
        """'none' effect should stop engine and set static color."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        apply_effect_selection(mock_tray, effect_name="none")

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_color.assert_called_once_with(
            mock_tray.config.color, brightness=mock_tray.config.brightness
        )
        assert mock_tray.config.effect == "none"
        assert mock_tray.is_off is False

    def test_stop_effect_behaves_like_none(self):
        """'stop' effect should behave the same as 'none'."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        apply_effect_selection(mock_tray, effect_name="stop")

        mock_tray.engine.stop.assert_called_once()
        assert mock_tray.config.effect == "none"
        assert mock_tray.is_off is False

    def test_hardware_effect_blocked_when_not_supported(self):
        """Hardware effects should fall back to 'none' if not supported."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(hardware_effects=False, per_key=True)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        apply_effect_selection(mock_tray, effect_name="rainbow")

        # Should fall back to static color
        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_color.assert_called_once()
        assert mock_tray.config.effect == "none"

    def test_perkey_effect_blocked_when_not_supported(self):
        """Per-key effects should fall back to 'none' if not supported."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(per_key=False, hardware_effects=True)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        apply_effect_selection(mock_tray, effect_name="perkey")

        # Should fall back to static color
        mock_tray.engine.stop.assert_called_once()
        assert mock_tray.config.effect == "none"

    def test_perkey_effect_loads_colors_when_supported(self, monkeypatch):
        """Per-key effect should explicitly load colors from profile when per-key is supported."""
        from src.tray.controllers import effect_selection
        from src.tray.controllers.effect_selection import apply_effect_selection

        # Mock profile loading
        expected_colors = {(0, 0): (255, 0, 0)}
        load_spy = MagicMock(return_value=expected_colors)
        monkeypatch.setattr(effect_selection, "_load_per_key_colors_from_profile", load_spy)

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(per_key=True)
        mock_tray.config.per_key_colors = {}

        apply_effect_selection(mock_tray, effect_name="perkey")

        assert mock_tray.config.effect == "perkey"
        load_spy.assert_called_once()
        assert mock_tray.config.per_key_colors == expected_colors
        mock_tray._start_current_effect.assert_called_once()

    def test_regular_effect_starts_engine_normally(self):
        """Regular supported effects should start the engine normally."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(hardware_effects=True, per_key=True)

        apply_effect_selection(mock_tray, effect_name="wave")

        assert mock_tray.config.effect == "wave"
        mock_tray._start_current_effect.assert_called_once()

    def test_defaults_to_support_all_when_caps_missing(self):
        """Should assume all capabilities supported if backend_caps is None."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = None

        # Both hardware and per-key effects should work
        apply_effect_selection(mock_tray, effect_name="rainbow")
        assert mock_tray.config.effect == "rainbow"

        apply_effect_selection(mock_tray, effect_name="perkey")
        assert mock_tray.config.effect == "perkey"

    def test_hardware_effects_list_blocked_correctly(self):
        """All hardware effects in the list should be blocked when not supported."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(hardware_effects=False, per_key=True)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        hw_effects = ["rainbow", "breathing", "wave", "ripple", "marquee", "raindrop", "aurora", "fireworks"]

        for effect in hw_effects:
            apply_effect_selection(mock_tray, effect_name=effect)
            assert mock_tray.config.effect == "none", f"{effect} should be blocked"

    def test_stop_sets_uniform_color(self):
        """Stopping an effect should set uniform color when no per-key colors."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(hardware_effects=True, per_key=True)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)
        mock_tray.config.color = (255, 0, 0)
        mock_tray.config.brightness = 100

        # Start from no per-key colors.
        mock_tray.config.effect = "wave"
        mock_tray.config.per_key_colors = {}  # Empty = hardware mode

        # Stop effects; should set uniform color.
        apply_effect_selection(mock_tray, effect_name="none")

        mock_tray.engine.stop.assert_called()
        mock_tray.engine.kb.set_color.assert_called_with((255, 0, 0), brightness=100)
        assert mock_tray.config.effect == "none"

    def test_stop_stays_in_software_mode_if_perkey_colors_exist(self):
        """Stopping an effect should stay in software mode if per-key colors exist."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(hardware_effects=True, per_key=True)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        # Start from per-key with colors loaded.
        mock_tray.config.effect = "reactive_fade"
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}

        # Stop effects; should stay in software mode with static per-key.
        apply_effect_selection(mock_tray, effect_name="none")

        mock_tray.engine.stop.assert_called()
        assert mock_tray.config.effect == "perkey"
        mock_tray._start_current_effect.assert_called_once()

    def test_hw_uniform_forces_hardware_mode_even_if_perkey_colors_exist(self):
        """Selecting hardware uniform should clear per-key gating and unlock HW mode."""
        from src.tray.controllers.effect_selection import apply_effect_selection

        mock_tray = MagicMock()
        mock_tray.backend_caps = MagicMock(hardware_effects=True, per_key=True)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        # Start from software mode with per-key colors loaded.
        mock_tray.config.effect = "perkey"
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}

        apply_effect_selection(mock_tray, effect_name="hw_uniform")

        mock_tray.engine.stop.assert_called()
        assert mock_tray.config.effect == "none"
        assert mock_tray.config.per_key_colors == {}
        mock_tray.engine.kb.set_color.assert_called_once_with(
            mock_tray.config.color, brightness=mock_tray.config.brightness
        )
        assert mock_tray.is_off is False
