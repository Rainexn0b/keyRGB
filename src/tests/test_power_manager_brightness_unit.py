"""Unit tests for PowerManager brightness application paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


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
        from src.core.config import Config
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        del mock_kb.apply_brightness_from_power_policy
        mock_kb.engine = MagicMock()

        cfg = Config()
        cfg.brightness = 50

        pm = PowerManager(mock_kb, config=cfg)
        pm._apply_brightness_policy(75)

        mock_kb.engine.set_brightness.assert_called_once_with(75)

    def test_apply_brightness_handles_missing_engine_gracefully(self):
        """If engine is missing or raises, don't crash."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock(spec=[])

        pm = PowerManager(mock_kb)
        pm._apply_brightness_policy(60)

    def test_apply_brightness_ignores_negative_values(self):
        """Negative brightness is a no-op."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.apply_brightness_from_power_policy = MagicMock()

        pm = PowerManager(mock_kb)
        pm._apply_brightness_policy(-10)

        mock_kb.apply_brightness_from_power_policy.assert_not_called()


class TestPowerManagerApplyBrightnessExceptionPaths:
    def test_apply_brightness_policy_handles_config_set_exception(self):
        from src.core.power_management.manager import PowerManager

        class _ConfigRaisingOnSet:
            def reload(self):
                return None

            @property
            def brightness(self):
                return 50

            @brightness.setter
            def brightness(self, _value):
                raise RuntimeError("nope")

        mock_kb = MagicMock(spec=["engine"])
        mock_kb.engine = MagicMock()

        pm = PowerManager(mock_kb, config=_ConfigRaisingOnSet())
        pm._apply_brightness_policy(10)

        mock_kb.engine.set_brightness.assert_called_once_with(10)

    def test_apply_brightness_policy_logs_if_engine_set_brightness_raises(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock(spec=["engine"])
        mock_kb.engine = MagicMock()
        mock_kb.engine.set_brightness = MagicMock(side_effect=RuntimeError("boom"))

        pm = PowerManager(mock_kb)

        with patch("src.core.power_management.manager.logger.exception") as exc:
            pm._apply_brightness_policy(10)

        exc.assert_called_once()
