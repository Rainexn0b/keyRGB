#!/usr/bin/env python3
"""Unit tests for PowerManager (core/power_management/manager.py).

Tests power event handling, brightness policy, and config-gated behavior
without real hardware or blocking I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPowerManagerBrightnessPolicyApplication:
    """Test _apply_brightness_policy dispatch logic."""

    def test_apply_brightness_uses_controller_hook_if_present(self):
        """If kb_controller has apply_brightness_from_power_policy, prefer it."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.apply_brightness_from_power_policy = MagicMock()

        pm = PowerManager(mock_kb)
        pm._apply_brightness_policy(50)

        mock_kb.apply_brightness_from_power_policy.assert_called_once_with(50)

    def test_apply_brightness_fallback_to_engine_if_no_hook(self):
        """If no dedicated hook, fall back to config + engine.set_brightness."""
        from src.core.power_management.manager import PowerManager
        from src.core.config import Config

        mock_kb = MagicMock()
        del mock_kb.apply_brightness_from_power_policy
        mock_kb.engine = MagicMock()

        # Use a fresh config with explicit brightness
        cfg = Config()
        cfg.brightness = 50

        pm = PowerManager(mock_kb, config=cfg)
        pm._apply_brightness_policy(75)

        # Should call engine.set_brightness (config update may fail silently)
        mock_kb.engine.set_brightness.assert_called_once_with(75)

    def test_apply_brightness_handles_missing_engine_gracefully(self):
        """If engine is missing or raises, don't crash."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock(spec=[])  # no apply_brightness_from_power_policy, no engine

        pm = PowerManager(mock_kb)
        # Should not raise
        pm._apply_brightness_policy(60)

    def test_apply_brightness_ignores_negative_values(self):
        """Negative brightness is a no-op."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.apply_brightness_from_power_policy = MagicMock()

        pm = PowerManager(mock_kb)
        pm._apply_brightness_policy(-10)

        mock_kb.apply_brightness_from_power_policy.assert_not_called()


class TestPowerManagerConfigGating:
    """Test that power management actions respect enable flags."""

    def test_is_enabled_returns_true_when_config_flag_is_true(self):
        """When power_management_enabled is True, _is_enabled returns True."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True

        assert pm._is_enabled() is True

    def test_is_enabled_returns_false_when_config_flag_is_false(self):
        """When power_management_enabled is False, _is_enabled returns False."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = False

        assert pm._is_enabled() is False

    def test_is_enabled_defaults_to_true_on_missing_attribute(self):
        """If config has no power_management_enabled attr, fail open (True)."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_config = MagicMock()
        # Simulate missing attribute
        del mock_config.power_management_enabled
        mock_config.reload = MagicMock()

        pm = PowerManager(mock_kb, config=mock_config)
        # Should default to True
        assert pm._is_enabled() is True

    def test_is_enabled_defaults_to_true_on_reload_exception(self):
        """If config.reload() raises, _is_enabled fails open (True)."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.reload = MagicMock(side_effect=RuntimeError("boom"))

        assert pm._is_enabled() is True

    def test_flag_returns_default_on_reload_exception(self):
        """If config.reload() raises, _flag returns provided default."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.reload = MagicMock(side_effect=OSError("file gone"))

        assert pm._flag("some_flag", default=False) is False
        assert pm._flag("other_flag", default=True) is True


class TestPowerManagerEventHandlers:
    """Test lid/suspend event handlers."""

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_suspend_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_suspend should call kb.turn_off() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_instance.handle_power_off_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_off_on_suspend = True

        pm._on_suspend()

        mock_kb.turn_off.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_suspend_skips_when_disabled(self, mock_policy_cls):
        """_on_suspend should not call turn_off when power_management_enabled=False."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = False

        pm._on_suspend()

        mock_kb.turn_off.assert_not_called()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_resume_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_resume should call kb.restore() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            RestoreFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_instance.handle_power_restore_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_restore_on_resume = True

        # Patch time.sleep to avoid delay in test
        with patch("time.sleep"):
            pm._on_resume()

        mock_kb.restore.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_lid_close_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_lid_close should call kb.turn_off() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_instance.handle_power_off_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_off_on_lid_close = True

        pm._on_lid_close()

        mock_kb.turn_off.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_lid_open_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_lid_open should call kb.restore() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            RestoreFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_instance.handle_power_restore_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_restore_on_lid_open = True

        pm._on_lid_open()

        mock_kb.restore.assert_called_once()

    def test_handle_power_event_catches_exceptions_in_kb_methods(self):
        """If kb.turn_off/restore raises, _handle_power_event should not crash."""
        from src.core.power_management.manager import (
            PowerManager,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=RuntimeError("hardware error"))

        with patch("src.core.power_management.manager.PowerEventPolicy") as mock_policy_cls:
            mock_policy_instance = MagicMock()
            mock_result = MagicMock(actions=[TurnOffFromEvent()])
            mock_policy_instance.handle_power_off_event.return_value = mock_result
            mock_policy_cls.return_value = mock_policy_instance

            pm = PowerManager(mock_kb)
            pm._config.power_management_enabled = True
            pm._config.power_off_on_suspend = True

            # Should not raise
            pm._on_suspend()
