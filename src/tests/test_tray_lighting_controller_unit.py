#!/usr/bin/env python3
"""Unit tests for tray lighting controller (tray/controllers/lighting_controller.py).

Tests decision logic for effect switching, brightness management, and on/off state.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestParseMenInt:
    """Test _parse_menu_int helper."""

    def test_parse_menu_int_strips_radio_markers(self):
        """Should strip radio button markers and parse int."""
        from src.tray.controllers.lighting_controller import _parse_menu_int

        assert _parse_menu_int("🔘 50") == 50
        assert _parse_menu_int("⚪ 75") == 75
        assert _parse_menu_int("100") == 100

    def test_parse_menu_int_returns_none_on_invalid(self):
        """Should return None if string isn't parseable as int."""
        from src.tray.controllers.lighting_controller import _parse_menu_int

        assert _parse_menu_int("not a number") is None
        assert _parse_menu_int("🔘 abc") is None


class TestStartCurrentEffect:
    """Test start_current_effect effect dispatch logic."""

    def test_perkey_effect_calls_set_key_colors(self):
        """When effect='perkey', should call kb.set_key_colors."""
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 50
        mock_tray.config.per_key_colors = {(0, 0): (255, 0, 0)}
        mock_tray.engine.kb.enable_user_mode = MagicMock()
        mock_tray.engine.kb.set_key_colors = MagicMock()
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_key_colors.assert_called_once()
        assert mock_tray.is_off is False

    def test_perkey_turns_off_if_brightness_zero(self):
        """When effect='perkey' and brightness=0, should turn off."""
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "perkey"
        mock_tray.config.brightness = 0

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.turn_off.assert_called_once()
        assert mock_tray.is_off is True

    def test_none_effect_calls_set_color(self):
        """When effect='none', should call kb.set_color."""
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "none"
        mock_tray.config.brightness = 75
        mock_tray.config.color = (255, 0, 0)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)

        start_current_effect(mock_tray)

        mock_tray.engine.stop.assert_called_once()
        mock_tray.engine.kb.set_color.assert_called_once_with((255, 0, 0), brightness=75)
        assert mock_tray.is_off is False

    def test_animated_effect_starts_engine(self):
        """For animated effects (not 'perkey'/'none'), should call start_effect."""
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "breathe"
        mock_tray.config.brightness = 100
        mock_tray.config.speed = 3
        mock_tray.config.color = (0, 255, 0)
        mock_tray.config.reactive_color = None
        mock_tray.config.reactive_use_manual_color = False

        start_current_effect(mock_tray)

        mock_tray.engine.start_effect.assert_called_once_with(
            "breathe",
            speed=3,
            brightness=100,
            color=(0, 255, 0),
            reactive_color=None,
            reactive_use_manual_color=False,
        )
        assert mock_tray.is_off is False

    def test_start_current_effect_handles_exception_gracefully(self):
        """If effect start raises, should not crash."""
        from src.tray.controllers.lighting_controller import start_current_effect

        mock_tray = MagicMock()
        mock_tray.config.effect = "wave"
        mock_tray.engine.start_effect = MagicMock(side_effect=RuntimeError("hardware error"))

        # Should not raise
        start_current_effect(mock_tray)


class TestOnSpeedClicked:
    """Test on_speed_clicked menu handler."""

    def test_on_speed_clicked_updates_config_and_restarts_effect(self):
        """Should update config.speed and restart effect if not off."""
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.speed = 1
        mock_tray.config.effect = "breathe"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "🔘 5")

        assert mock_tray.config.speed == 5
        mock_start.assert_called_once_with(mock_tray)
        mock_tray._update_menu.assert_called_once()

    def test_on_speed_clicked_skips_restart_if_off(self):
        """If tray.is_off, should not restart effect."""
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = True

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_speed_clicked(mock_tray, "3")

        assert mock_tray.config.speed == 3
        mock_start.assert_not_called()

    def test_on_speed_clicked_ignores_invalid_input(self):
        """If item can't be parsed as int, should do nothing."""
        from src.tray.controllers.lighting_controller import on_speed_clicked

        mock_tray = MagicMock()
        original_speed = mock_tray.config.speed

        on_speed_clicked(mock_tray, "not a number")

        # Speed should not change
        assert mock_tray.config.speed == original_speed


class TestOnBrightnessClicked:
    """Test on_brightness_clicked menu handler."""

    def test_on_brightness_clicked_updates_config_and_restarts(self):
        """Should update config.brightness, call set_brightness, and restart."""
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_brightness_clicked(mock_tray, "🔘 20")

        # 20 * 5 = 100
        assert mock_tray.config.brightness == 100
        mock_tray.engine.set_brightness.assert_called_once_with(100, apply_to_hardware=True)
        mock_start.assert_called_once_with(mock_tray)

    def test_on_brightness_clicked_does_not_restart_software_effect(self):
        """Software effects should update brightness in-place (no restart)."""
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray.config.effect = "rainbow_wave"  # software effect
        mock_tray.config.brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            on_brightness_clicked(mock_tray, "🔘 20")

        # 20 * 5 = 100
        assert mock_tray.config.brightness == 100
        mock_tray.engine.set_brightness.assert_called_once_with(100, apply_to_hardware=False)
        mock_start.assert_not_called()

    def test_on_brightness_clicked_saves_nonzero_to_last_brightness(self):
        """Non-zero brightness should be saved to _last_brightness."""
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray._last_brightness = 50

        with patch("src.tray.controllers.lighting_controller.start_current_effect"):
            on_brightness_clicked(mock_tray, "15")

        # 15 * 5 = 75
        assert mock_tray._last_brightness == 75

    def test_on_brightness_clicked_does_not_save_zero_to_last_brightness(self):
        """Zero brightness should not overwrite _last_brightness."""
        from src.tray.controllers.lighting_controller import on_brightness_clicked

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray._last_brightness = 100

        with patch("src.tray.controllers.lighting_controller.start_current_effect"):
            on_brightness_clicked(mock_tray, "0")

        # _last_brightness should remain 100
        assert mock_tray._last_brightness == 100


class TestTurnOffOn:
    """Test turn_off/turn_on user control logic."""

    def test_turn_off_sets_flags_and_calls_engine(self):
        """turn_off should set _user_forced_off and call engine.turn_off."""
        from src.tray.controllers.lighting_controller import turn_off

        mock_tray = MagicMock()
        mock_tray.is_off = False

        turn_off(mock_tray)

        assert mock_tray._user_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once()
        mock_tray._refresh_ui.assert_called_once()

    def test_turn_on_clears_flags_and_restores_brightness(self):
        """turn_on should clear forced_off flags and restore brightness if zero."""
        from src.tray.controllers.lighting_controller import turn_on

        mock_tray = MagicMock()
        mock_tray.is_off = True
        mock_tray.config.brightness = 0
        mock_tray._last_brightness = 75
        mock_tray.config.effect = "breathe"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            turn_on(mock_tray)

        assert mock_tray._user_forced_off is False
        assert mock_tray._idle_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 75
        mock_start.assert_called_once_with(mock_tray)

    def test_turn_on_uses_default_25_if_no_last_brightness(self):
        """If _last_brightness is also zero, use default 25."""
        from src.tray.controllers.lighting_controller import turn_on

        mock_tray = MagicMock()
        mock_tray.is_off = True
        mock_tray.config.brightness = 0
        mock_tray._last_brightness = 0
        mock_tray.config.effect = "none"
        mock_tray.config.color = (255, 255, 255)
        mock_tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)

        turn_on(mock_tray)

        assert mock_tray.config.brightness == 25


class TestPowerTurnOffRestore:
    """Test power_turn_off/power_restore logic."""

    def test_power_turn_off_sets_power_forced_flag(self):
        """power_turn_off should set _power_forced_off."""
        from src.tray.controllers.lighting_controller import power_turn_off

        mock_tray = MagicMock()
        mock_tray.is_off = False

        power_turn_off(mock_tray)

        assert mock_tray._power_forced_off is True
        assert mock_tray._idle_forced_off is False
        assert mock_tray.is_off is True
        mock_tray.engine.turn_off.assert_called_once()

    def test_power_restore_restores_when_power_forced(self):
        """power_restore should restore when _power_forced_off was True."""
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._user_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = True
        mock_tray.is_off = True
        mock_tray.config.brightness = 0
        mock_tray._last_brightness = 50
        mock_tray.config.effect = "breathe"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        assert mock_tray._power_forced_off is False
        assert mock_tray.is_off is False
        assert mock_tray.config.brightness == 50
        mock_start.assert_called_once_with(mock_tray)

    def test_power_restore_restores_when_off_due_to_hardware_reset(self):
        """If the tray is off but not user-forced, restore should reapply state."""
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._power_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._user_forced_off = False
        mock_tray.is_off = True
        mock_tray.config.brightness = 25
        mock_tray.config.effect = "none"

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        assert mock_tray.is_off is False
        mock_start.assert_called_once_with(mock_tray)

    def test_power_restore_does_not_fight_user_forced_off(self):
        """If the user explicitly turned off lighting, restore is a no-op."""
        from src.tray.controllers.lighting_controller import power_restore

        mock_tray = MagicMock()
        mock_tray._user_forced_off = True
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = False
        mock_tray.is_off = True
        mock_tray.config.brightness = 25

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            power_restore(mock_tray)

        mock_start.assert_not_called()


class TestApplyBrightnessFromPowerPolicy:
    """Test apply_brightness_from_power_policy behavior."""

    def test_apply_brightness_from_power_policy_restarts_non_software_effect(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray._user_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = False
        mock_tray.config.effect = "breathe"  # not a software effect
        mock_tray.config.brightness = 50

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.brightness == 25
        mock_tray.engine.set_brightness.assert_called_once_with(25, apply_to_hardware=True)
        mock_start.assert_called_once_with(mock_tray)

    def test_apply_brightness_from_power_policy_does_not_restart_software_effect(self):
        from src.tray.controllers.lighting_controller import apply_brightness_from_power_policy

        mock_tray = MagicMock()
        mock_tray.is_off = False
        mock_tray._user_forced_off = False
        mock_tray._idle_forced_off = False
        mock_tray._power_forced_off = False
        mock_tray.config.effect = "rainbow_wave"  # software effect
        mock_tray.config.brightness = 50

        with patch("src.tray.controllers.lighting_controller.start_current_effect") as mock_start:
            apply_brightness_from_power_policy(mock_tray, 25)

        assert mock_tray.config.brightness == 25
        mock_tray.engine.set_brightness.assert_called_once_with(25, apply_to_hardware=False)
        mock_start.assert_not_called()
