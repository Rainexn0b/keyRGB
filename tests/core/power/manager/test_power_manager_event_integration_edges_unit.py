"""Disabled-config gating, no-op plan, and edge-case tests for PowerManager event path.

Split from test_power_manager_event_integration_seam_unit.py to keep files
focused. Covers the tail orchestration chain:

  _handle_power_event() → _evaluate_power_event_policy() →
  _execute_power_event_plan() → _invoke_keyboard_method()

Focus: disabled gating, no-op plans, and component interactions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent
from keyrgb.core.power.policies.power_event_policy import PowerEventInputs, PowerEventResult


class TestPowerManagerDisabledConfigGating:
    """Disabled config: flow short-circuits early, no side effects."""

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_disabled_still_allows_policy_state_cleanup(self, mock_policy_cls):
        """Disabled events reach policy cleanup but cannot touch hardware."""
        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=(TurnOffFromEvent(),))
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = False

        pm._handle_power_event(
            enabled=False,
            action_enabled=True,
            log_message="Should not see this",
            policy_method=mock_policy_instance.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

        inputs = mock_policy_instance.handle_power_off_event.call_args.args[0]
        assert inputs.enabled is False
        # No keyboard action
        mock_kb.turn_off.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_early_exit_when_action_enabled_false_no_policy_call(self, mock_policy_cls):
        """action_enabled=False still allows policy to be called (to track state).

        This is important for lid close/open: we track state even if action is disabled,
        to decide whether to restore on the matching open/resume event.
        """
        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = False  # Action disabled

        pm._handle_power_event(
            enabled=True,
            action_enabled=False,  # Action disabled
            log_message="Should not execute",
            policy_method=mock_policy_instance.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

        # Policy WAS called (to track state)
        assert mock_policy_instance.handle_power_off_event.call_count == 1

        # But no keyboard action (empty plan)
        mock_kb.turn_off.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_no_logs_when_disabled(self, mock_policy_cls):
        """When enabled=False, no logging should occur."""
        from keyrgb.core.power.management.manager import logger

        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = False

        with patch.object(logger, "info") as log_info_mock:
            pm._handle_power_event(
                enabled=False,
                action_enabled=True,
                log_message="Should not log",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        # No info logs (only exception logs from errors)
        log_info_mock.assert_not_called()


class TestPowerManagerNoOpPlanExecution:
    """No-op plan: action_count=0, no side effects."""

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_noop_when_policy_returns_no_actions(self, mock_policy_cls):
        """Policy returns empty actions → no side effects."""
        from keyrgb.core.power.management.manager import logger

        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        # Empty actions (no turn-off planned)
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with (
            patch.object(logger, "info") as log_info_mock,
            patch("keyrgb.core.power.management.manager.time.sleep") as sleep_mock,
        ):
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Should not log",
                delay_s=0.5,
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        # No logging (empty plan, should_log=False)
        log_info_mock.assert_not_called()

        # No sleep
        sleep_mock.assert_not_called()

        # No keyboard action
        mock_kb.turn_off.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_noop_plan_returns_cleanly(self, mock_policy_cls):
        """No-op plan execution returns cleanly (no side effects, no logs, no error)."""
        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        # Should not raise
        try:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Ignored",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )
        except Exception as e:  # noqa: BLE001 - convert any unexpected raise into pytest.fail
            pytest.fail(f"_handle_power_event raised {type(e).__name__}: {e}")

        # Verify no side effects
        mock_kb.turn_off.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_action_count_zero_no_invocation_even_with_log(self, mock_policy_cls):
        """Even with should_log=True, action_count=0 means no invocation."""
        from keyrgb.core.power.management.manager import logger

        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        # This shouldn't happen in practice, but test robustness: 0 actions means no invoke
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        with (
            patch.object(logger, "info") as log_info_mock,
            patch("keyrgb.core.power.management.manager.time.sleep") as sleep_mock,
        ):
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Testing",
                delay_s=0.1,
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        # No log, no sleep, no invocation (action_count=0 gates everything)
        log_info_mock.assert_not_called()
        sleep_mock.assert_not_called()
        mock_kb.turn_off.assert_not_called()


class TestPowerManagerEventIntegrationEdgeCases:
    """Edge cases and interactions between components."""

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_with_zero_delay_skips_sleep(self, mock_policy_cls):
        """Delay of 0.0 or negative should not call sleep."""
        from keyrgb.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=(TurnOffFromEvent(),))
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with patch.object(logger, "info"), patch("keyrgb.core.power.management.manager.time.sleep") as sleep_mock:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test",
                delay_s=0.0,
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        # Sleep should NOT be called when delay is 0
        sleep_mock.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_multiple_actions_invokes_per_count(self, mock_policy_cls):
        """Plan with action_count=N should invoke kb method N times."""
        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        # 5 turn-off actions
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=(TurnOffFromEvent(),) * 5)
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="Test",
            policy_method=mock_policy_instance.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

        # Invoked 5 times
        assert mock_kb.turn_off.call_count == 5

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_evaluate_policy_passes_correct_power_event_inputs(self, mock_policy_cls):
        """Policy receives PowerEventInputs with correct enabled/action_enabled/is_off."""
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb._user_forced_off = True
        mock_kb.tray_idle_power_state = TrayIdlePowerState(user_forced_off=True)

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        pm._handle_power_event(
            enabled=True,
            action_enabled=False,
            log_message="Test",
            policy_method=mock_policy_instance.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

        # Verify inputs passed to policy
        call_args = mock_policy_instance.handle_power_off_event.call_args[0][0]
        assert isinstance(call_args, PowerEventInputs)
        assert call_args.enabled is True
        assert call_args.action_enabled is False
        # is_off should be True (from mock_kb.is_off and mock_kb._user_forced_off)
        assert call_args.is_off is True
