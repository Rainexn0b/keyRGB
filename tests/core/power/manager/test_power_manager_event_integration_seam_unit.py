"""Integration-seam tests for PowerManager power event delegate path.

Tests the full orchestration chain:
  _handle_power_event() → _evaluate_power_event_policy() →
  _execute_power_event_plan() → _invoke_keyboard_method()

Focus: error recovery at runtime boundaries and full happy path.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.core.power.management.manager import PowerManager, TurnOffFromEvent, RestoreFromEvent
from src.core.power.policies.power_event_policy import PowerEventInputs, PowerEventResult


class TestPowerManagerEventIntegrationFullPath:
    """Happy path: full event orchestration with real policy objects."""

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_full_path_with_turnoff_action(self, mock_policy_cls):
        """_handle_power_event orchestrates: policy eval → plan build → execute."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb._user_forced_off = False
        mock_kb.turn_off = MagicMock()

        # Create a real mock policy that returns turn-off action
        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(
            actions=(TurnOffFromEvent(),) * 2  # 2 actions for verification
        )
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with patch.object(logger, "info") as log_info_mock:
            with patch("src.core.power.management.manager.time.sleep") as sleep_mock:
                pm._handle_power_event(
                    enabled=True,
                    action_enabled=True,
                    log_message="Test suspend event",
                    delay_s=0.1,
                    policy_method=mock_policy_instance.handle_power_off_event,
                    expected_action_type=TurnOffFromEvent,
                    kb_method_name="turn_off",
                )

        # Verify full chain:
        # 1. Policy was called with correct inputs
        assert mock_policy_instance.handle_power_off_event.call_count == 1
        call_inputs = mock_policy_instance.handle_power_off_event.call_args[0][0]
        assert isinstance(call_inputs, PowerEventInputs)

        # 2. Plan was built and executed (2 turn-off actions)
        assert mock_kb.turn_off.call_count == 2

        # 3. Logging occurred
        log_info_mock.assert_called_once_with("Test suspend event")

        # 4. Sleep was called with correct delay
        sleep_mock.assert_called_once_with(0.1)

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_full_path_with_restore_action(self, mock_policy_cls):
        """_handle_power_event with restore action (resume event)."""
        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = PowerEventResult(
            actions=(RestoreFromEvent(),)
        )
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_restore_on_resume = True

        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="Test resume event",
            delay_s=0.5,
            policy_method=mock_policy_instance.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )

        # Verify restore was called
        assert mock_kb.restore.call_count == 1
        # Policy eval was called
        assert mock_policy_instance.handle_power_restore_event.call_count == 1


class TestPowerManagerPolicyEvaluationBoundaryErrorRecovery:
    """Policy evaluation boundary: catch and log errors, continue gracefully."""

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_evaluate_policy_catches_attribute_error_and_logs(self, mock_policy_cls):
        """RuntimeError during policy method should be caught, logged, not propagated."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb._user_forced_off = False

        mock_policy_instance = MagicMock()
        # Simulate policy method raising an error
        mock_policy_instance.handle_power_off_event.side_effect = AttributeError("missing attr")
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        with patch.object(logger, "exception") as log_exc_mock:
            # This should NOT raise; should catch and log
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test event",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        # Error was caught and logged
        assert log_exc_mock.call_count == 1
        assert "Power event policy evaluation failed" in log_exc_mock.call_args[0][0]

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_continues_after_policy_error(self, mock_policy_cls):
        """After policy error, _handle_power_event returns cleanly (no crash)."""
        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.side_effect = RuntimeError("policy boom")
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        # No exception should propagate; method should return cleanly
        try:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )
        except Exception as e:
            pytest.fail(f"_handle_power_event raised {type(e).__name__}: {e}")

        # Keyboard was NOT called (plan was None due to error)
        mock_kb.turn_off.assert_not_called()

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_evaluate_policy_catches_lookup_error(self, mock_policy_cls):
        """LookupError during policy eval should also be caught and logged."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb._user_forced_off = False

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.side_effect = LookupError("not found")
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        with patch.object(logger, "exception") as log_exc_mock:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        assert log_exc_mock.call_count == 1


class TestPowerManagerKeyboardMethodInvocationBoundaryErrorRecovery:
    """Keyboard invocation boundary: catch per-invocation errors, continue loop."""

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_execute_plan_catches_runtime_error_per_invocation(self, mock_policy_cls):
        """RuntimeError in kb method should be caught, logged per invocation."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()

        # First call raises, second call succeeds
        mock_kb.turn_off = MagicMock(side_effect=[RuntimeError("first fails"), None])

        mock_policy_instance = MagicMock()
        # 2 turn-off actions in the plan
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(
            actions=(TurnOffFromEvent(),) * 2
        )
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with patch.object(logger, "exception") as log_exc_mock:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test event",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        # Both invocations were attempted
        assert mock_kb.turn_off.call_count == 2

        # First failure was logged
        assert log_exc_mock.call_count == 1
        assert "Power event keyboard action 'turn_off' failed" in log_exc_mock.call_args[0][0]

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_execute_plan_continues_after_invocation_error(self, mock_policy_cls):
        """Flow continues even when kb method raises (per action, not halt)."""
        mock_kb = MagicMock()
        # All 3 calls fail, but they should all be attempted
        mock_kb.turn_off = MagicMock(
            side_effect=[RuntimeError("fail1"), RuntimeError("fail2"), RuntimeError("fail3")]
        )

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(
            actions=(TurnOffFromEvent(),) * 3
        )
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        # Should not raise; all 3 should be attempted
        try:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )
        except Exception as e:
            pytest.fail(f"_handle_power_event raised {type(e).__name__}: {e}")

        # All 3 invocations were attempted despite errors
        assert mock_kb.turn_off.call_count == 3

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_execute_plan_catches_type_error_in_kb_method(self, mock_policy_cls):
        """TypeError in kb method should also be caught and logged."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock(side_effect=TypeError("wrong arg type"))

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(
            actions=(TurnOffFromEvent(),)
        )
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with patch.object(logger, "exception") as log_exc_mock:
            pm._handle_power_event(
                enabled=True,
                action_enabled=True,
                log_message="Test",
                policy_method=mock_policy_instance.handle_power_off_event,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        assert log_exc_mock.call_count == 1


class TestPowerManagerDisabledConfigGating:
    """Disabled config: flow short-circuits early, no side effects."""

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_early_exit_when_enabled_is_false(self, mock_policy_cls):
        """When enabled=False, orchestrate should return early (no policy call)."""
        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
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

        # Policy was NOT called
        mock_policy_instance.handle_power_off_event.assert_not_called()
        # No keyboard action
        mock_kb.turn_off.assert_not_called()

    @patch("src.core.power.management.manager.PowerEventPolicy")
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

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_no_logs_when_disabled(self, mock_policy_cls):
        """When enabled=False, no logging should occur."""
        from src.core.power.management.manager import logger

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

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_noop_when_policy_returns_no_actions(self, mock_policy_cls):
        """Policy returns empty actions → no side effects."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        # Empty actions (no turn-off planned)
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with patch.object(logger, "info") as log_info_mock:
            with patch("src.core.power.management.manager.time.sleep") as sleep_mock:
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

    @patch("src.core.power.management.manager.PowerEventPolicy")
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
        except Exception as e:
            pytest.fail(f"_handle_power_event raised {type(e).__name__}: {e}")

        # Verify no side effects
        mock_kb.turn_off.assert_not_called()

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_action_count_zero_no_invocation_even_with_log(self, mock_policy_cls):
        """Even with should_log=True, action_count=0 means no invocation."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()

        mock_policy_instance = MagicMock()
        # This shouldn't happen in practice, but test robustness: 0 actions means no invoke
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=())
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True

        with patch.object(logger, "info") as log_info_mock:
            with patch("src.core.power.management.manager.time.sleep") as sleep_mock:
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

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_with_zero_delay_skips_sleep(self, mock_policy_cls):
        """Delay of 0.0 or negative should not call sleep."""
        from src.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(
            actions=(TurnOffFromEvent(),)
        )
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        with patch.object(logger, "info"):
            with patch("src.core.power.management.manager.time.sleep") as sleep_mock:
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

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_multiple_actions_invokes_per_count(self, mock_policy_cls):
        """Plan with action_count=N should invoke kb method N times."""
        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        # 5 turn-off actions
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(
            actions=(TurnOffFromEvent(),) * 5
        )
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

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_evaluate_policy_passes_correct_power_event_inputs(self, mock_policy_cls):
        """Policy receives PowerEventInputs with correct enabled/action_enabled/is_off."""
        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb._user_forced_off = True

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
