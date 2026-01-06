"""Unit tests for PowerManager config gating."""

from __future__ import annotations

from unittest.mock import MagicMock


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
        del mock_config.power_management_enabled
        mock_config.reload = MagicMock()

        pm = PowerManager(mock_kb, config=mock_config)
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
