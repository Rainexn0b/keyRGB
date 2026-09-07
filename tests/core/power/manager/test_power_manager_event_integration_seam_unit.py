"""Integration-seam tests for PowerManager power event delegate path.

Tests the full orchestration chain:
  _handle_power_event() → _evaluate_power_event_policy() →
  _execute_power_event_plan() → _invoke_keyboard_method()

Focus: error recovery at runtime boundaries and full happy path.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent, TurnOffFromEvent
from keyrgb.core.power.policies.power_event_policy import PowerEventInputs, PowerEventResult


class TestPowerManagerEventIntegrationFullPath:
    """Happy path: full event orchestration with real policy objects."""

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_full_path_with_turnoff_action(self, mock_policy_cls):
        """_handle_power_event orchestrates: policy eval → plan build → execute."""
        from keyrgb.core.power.management.manager import logger
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb._user_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(user_forced_off=False)
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

        with (
            patch.object(logger, "info") as log_info_mock,
            patch("keyrgb.core.power.management.manager.time.sleep") as sleep_mock,
        ):
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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_handle_power_event_full_path_with_restore_action(self, mock_policy_cls):
        """_handle_power_event with restore action (resume event)."""
        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = PowerEventResult(actions=(RestoreFromEvent(),))
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

    def test_disabled_resume_clears_saved_intent_without_restoring_later(self):
        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        mock_kb.restore = MagicMock()
        pm = PowerManager(mock_kb, config=MagicMock())
        pm._get_keyboard_intent_state = MagicMock(side_effect=[False, True, True])

        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="cycle one suspend",
            policy_method=pm._event_policy.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        pm._handle_power_event(
            enabled=False,
            action_enabled=True,
            log_message="disabled resume",
            policy_method=pm._event_policy.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )
        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="cycle two suspend",
            policy_method=pm._event_policy.handle_power_off_event,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="cycle two resume",
            policy_method=pm._event_policy.handle_power_restore_event,
            expected_action_type=RestoreFromEvent,
            kb_method_name="restore",
        )

        assert mock_kb.turn_off.call_count == 2
        mock_kb.restore.assert_not_called()
        assert pm._get_keyboard_intent_state.call_count == 3


class TestPowerManagerPolicyEvaluationBoundaryErrorRecovery:
    """Policy evaluation boundary: catch and log errors, continue gracefully."""

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_evaluate_policy_catches_attribute_error_and_logs(self, mock_policy_cls):
        """RuntimeError during policy method should be caught, logged, not propagated."""
        from keyrgb.core.power.management.manager import logger
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb._user_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(user_forced_off=False)

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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
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
        except Exception as e:  # noqa: BLE001 - convert any unexpected raise into pytest.fail
            pytest.fail(f"_handle_power_event raised {type(e).__name__}: {e}")

        # Keyboard was NOT called (plan was None due to error)
        mock_kb.turn_off.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_evaluate_policy_catches_lookup_error(self, mock_policy_cls):
        """LookupError during policy eval should also be caught and logged."""
        from keyrgb.core.power.management.manager import logger
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb._user_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(user_forced_off=False)

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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_execute_plan_catches_runtime_error_per_invocation(self, mock_policy_cls):
        """RuntimeError in kb method should be caught, logged per invocation."""
        from keyrgb.core.power.management.manager import logger

        mock_kb = MagicMock()

        # First call raises, second call succeeds
        mock_kb.turn_off = MagicMock(side_effect=[RuntimeError("first fails"), None])

        mock_policy_instance = MagicMock()
        # 2 turn-off actions in the plan
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=(TurnOffFromEvent(),) * 2)
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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_execute_plan_continues_after_invocation_error(self, mock_policy_cls):
        """Flow continues even when kb method raises (per action, not halt)."""
        mock_kb = MagicMock()
        # All 3 calls fail, but they should all be attempted
        mock_kb.turn_off = MagicMock(side_effect=[RuntimeError("fail1"), RuntimeError("fail2"), RuntimeError("fail3")])

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=(TurnOffFromEvent(),) * 3)
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
        except Exception as e:  # noqa: BLE001 - convert any unexpected raise into pytest.fail
            pytest.fail(f"_handle_power_event raised {type(e).__name__}: {e}")

        # All 3 invocations were attempted despite errors
        assert mock_kb.turn_off.call_count == 3

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_execute_plan_catches_type_error_in_kb_method(self, mock_policy_cls):
        """TypeError in kb method should also be caught and logged."""
        from keyrgb.core.power.management.manager import logger

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock(side_effect=TypeError("wrong arg type"))

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = PowerEventResult(actions=(TurnOffFromEvent(),))
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
