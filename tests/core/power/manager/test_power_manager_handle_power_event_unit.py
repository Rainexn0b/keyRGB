"""Unit tests for PowerManager _handle_power_event branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class TestPowerManagerHandlePowerEventBranches:
    def test_handle_power_event_returns_when_policy_raises(self):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)

        with patch("keyrgb.core.power.management.manager.logger.exception") as exc:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="x",
                policy_method=MagicMock(side_effect=RuntimeError("boom")),
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        exc.assert_called_once()

    def test_handle_power_event_propagates_unexpected_policy_errors(self):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        pm = PowerManager(MagicMock())

        with pytest.raises(AssertionError, match="unexpected policy bug"):
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="x",
                policy_method=MagicMock(side_effect=AssertionError("unexpected policy bug")),
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

    def test_handle_power_event_filters_action_type_and_action_enabled(self):
        from keyrgb.core.power.management.manager import (
            PowerManager,
            RestoreFromEvent,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.brightness = 50

        result = SimpleNamespace(actions=[RestoreFromEvent(), TurnOffFromEvent()])
        policy_method = MagicMock(return_value=result)

        pm._handle_power_event(
            enabled=True,
            action_enabled=False,
            log_message="x",
            policy_method=policy_method,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        mock_kb.turn_off.assert_not_called()

        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="x",
            policy_method=policy_method,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        mock_kb.turn_off.assert_called_once()

    def test_handle_power_event_sleeps_and_logs_only_once_for_multiple_actions(self):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.brightness = 50

        result = SimpleNamespace(actions=[TurnOffFromEvent(), TurnOffFromEvent()])
        policy_method = MagicMock(return_value=result)

        with (
            patch("keyrgb.core.power.management.manager.time.sleep") as sleep,
            patch("keyrgb.core.power.management.manager.logger.info") as info,
        ):
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="hello",
                delay_s=0.25,
                policy_method=policy_method,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        sleep.assert_called_once_with(0.25)
        info.assert_called_once_with("hello")
        assert mock_kb.turn_off.call_count == 2

    def test_handle_power_event_reports_intent_off_from_user_flags_and_config(self):
        from keyrgb.core.power.management.manager import (
            PowerEventInputs,
            PowerManager,
            TurnOffFromEvent,
        )

        captured = {}

        def _policy(inputs: PowerEventInputs):
            captured["inputs"] = inputs
            return SimpleNamespace(actions=[])

        kb1 = MagicMock()
        kb1.user_forced_off = True
        pm1 = PowerManager(kb1)
        pm1._config.brightness = 50
        pm1._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="x",
            policy_method=_policy,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        assert captured["inputs"].is_off is True

        class _KbRaising:
            @property
            def user_forced_off(self):
                raise RuntimeError("boom")

            _user_forced_off = True

        pm2 = PowerManager(_KbRaising())
        pm2._config.brightness = 50
        pm2._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="x",
            policy_method=_policy,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        assert captured["inputs"].is_off is True

        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        kb3 = MagicMock()
        kb3.user_forced_off = False
        kb3._user_forced_off = False
        kb3.tray_idle_power_state = TrayIdlePowerState(user_forced_off=False)
        pm3 = PowerManager(kb3)
        pm3._config.brightness = 0
        pm3._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="x",
            policy_method=_policy,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        assert captured["inputs"].is_off is True
