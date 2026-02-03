"""Unit tests for PowerManager battery saver loop."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestPowerManagerBatterySaverLoop:
    def test_battery_saver_loop_covers_common_branches_and_actions(self):
        from src.core.power_management.manager import PowerManager
        from src.core.power_policies.power_source_loop_policy import (
            ApplyBrightness,
            RestoreKeyboard,
            TurnOffKeyboard,
        )

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        mock_kb.restore = MagicMock()
        mock_kb.is_off = False

        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.brightness = "not-an-int"
        cfg.power_management_enabled = True
        cfg.ac_lighting_enabled = True
        cfg.battery_lighting_enabled = True
        cfg.ac_lighting_brightness = None
        cfg.battery_lighting_brightness = None
        cfg.battery_saver_enabled = True
        cfg.battery_saver_brightness = 25

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True
        pm._apply_brightness_policy = MagicMock()

        result_skip = SimpleNamespace(skip=True, actions=[])
        result_actions = SimpleNamespace(
            skip=False,
            actions=[
                TurnOffKeyboard(),
                RestoreKeyboard(),
                ApplyBrightness(brightness=42),
            ],
        )
        fake_policy = MagicMock()
        fake_policy.update.side_effect = [result_skip, result_actions]

        on_ac_values = [None, True, True, True]

        sleep_calls = {"n": 0}

        def _sleep(_seconds):
            sleep_calls["n"] += 1
            if sleep_calls["n"] == 1:
                return
            if sleep_calls["n"] == 2:
                cfg.power_management_enabled = False
                return
            if sleep_calls["n"] == 3:
                cfg.power_management_enabled = True
                return
            pm.monitoring = False

        with (
            patch(
                "src.core.power_management.manager.read_on_ac_power",
                side_effect=on_ac_values,
            ),
            patch(
                "src.core.power_management.manager.PowerSourceLoopPolicy",
                return_value=fake_policy,
            ),
            patch(
                "src.core.power_management.manager.time.monotonic",
                return_value=123.0,
            ),
            patch(
                "src.core.power_management.manager.time.sleep",
                side_effect=_sleep,
            ),
        ):
            pm._battery_saver_loop()

        mock_kb.turn_off.assert_called_once()
        mock_kb.restore.assert_called_once()
        pm._apply_brightness_policy.assert_called_once_with(42)

    def test_battery_saver_loop_logs_and_continues_on_exception(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        cfg = MagicMock()
        cfg.reload = MagicMock()

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        def _sleep(_seconds):
            pm.monitoring = False

        with (
            patch(
                "src.core.power_management.manager.read_on_ac_power",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "src.core.power_management.manager.time.sleep",
                side_effect=_sleep,
            ),
            patch(
                "src.core.power_management.manager.logger.exception",
            ) as exc,
        ):
            pm._battery_saver_loop()

        exc.assert_called_once()
