"""Unit tests for PowerManager event-handler routing and policy seams."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPowerManagerEventHandlerRoutingSeams:
    def test_on_suspend_delegates_suspend_route_metadata_to_shared_helper(self):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        pm = PowerManager(MagicMock())

        with patch.object(pm, "_dispatch_power_event_route") as dispatch:
            pm._on_suspend()

        dispatch.assert_called_once()
        kwargs = dispatch.call_args.kwargs
        assert kwargs == {
            "flag_name": "power_off_on_suspend",
            "log_message": "System suspending - turning off keyboard backlight",
            "policy_method": kwargs["policy_method"],
            "expected_action_type": TurnOffFromEvent,
            "kb_method_name": "turn_off",
        }
        assert kwargs["policy_method"].__self__ is pm._event_policy
        assert kwargs["policy_method"].__name__ == "handle_power_off_event"

    def test_on_resume_delegates_restore_route_metadata_with_wakeup_delay(self):
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent

        pm = PowerManager(MagicMock())

        with patch.object(pm, "_dispatch_power_event_route") as dispatch:
            pm._on_resume()

        dispatch.assert_called_once()
        kwargs = dispatch.call_args.kwargs
        assert kwargs == {
            "flag_name": "power_restore_on_resume",
            "log_message": "System resumed - restoring keyboard backlight",
            "delay_s": 0.5,
            "policy_method": kwargs["policy_method"],
            "expected_action_type": RestoreFromEvent,
            "kb_method_name": "restore",
        }
        assert kwargs["policy_method"].__self__ is pm._event_policy
        assert kwargs["policy_method"].__name__ == "handle_power_restore_event"

    def test_on_lid_close_delegates_turn_off_route_metadata_to_shared_helper(self):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        pm = PowerManager(MagicMock())

        with patch.object(pm, "_dispatch_power_event_route") as dispatch:
            pm._on_lid_close()

        dispatch.assert_called_once()
        kwargs = dispatch.call_args.kwargs
        assert kwargs == {
            "flag_name": "power_off_on_lid_close",
            "log_message": "Lid closed - turning off keyboard backlight",
            "policy_method": kwargs["policy_method"],
            "expected_action_type": TurnOffFromEvent,
            "kb_method_name": "turn_off",
        }
        assert kwargs["policy_method"].__self__ is pm._event_policy
        assert kwargs["policy_method"].__name__ == "handle_power_off_event"

    def test_on_lid_open_delegates_restore_route_metadata_to_shared_helper(self):
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent

        pm = PowerManager(MagicMock())

        with patch.object(pm, "_dispatch_power_event_route") as dispatch:
            pm._on_lid_open()

        dispatch.assert_called_once()
        kwargs = dispatch.call_args.kwargs
        assert kwargs == {
            "flag_name": "power_restore_on_lid_open",
            "log_message": "Lid opened - restoring keyboard backlight",
            "policy_method": kwargs["policy_method"],
            "expected_action_type": RestoreFromEvent,
            "kb_method_name": "restore",
        }
        assert kwargs["policy_method"].__self__ is pm._event_policy
        assert kwargs["policy_method"].__name__ == "handle_power_restore_event"

    def test_dispatch_power_event_route_uses_enablement_and_flag_outputs_as_is(self):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        pm = PowerManager(MagicMock())
        enabled = object()
        action_enabled = object()
        policy_method = MagicMock()

        with (
            patch.object(pm, "_is_enabled", return_value=enabled) as is_enabled,
            patch.object(pm, "_flag", return_value=action_enabled) as flag,
            patch.object(pm, "_handle_power_event") as handle_power_event,
        ):
            pm._dispatch_power_event_route(
                flag_name="power_off_on_suspend",
                log_message="System suspending - turning off keyboard backlight",
                policy_method=policy_method,
                expected_action_type=TurnOffFromEvent,
                kb_method_name="turn_off",
            )

        is_enabled.assert_called_once_with()
        flag.assert_called_once_with("power_off_on_suspend", True)
        handle_power_event.assert_called_once_with(
            enabled=enabled,
            action_enabled=action_enabled,
            log_message="System suspending - turning off keyboard backlight",
            delay_s=0.0,
            policy_method=policy_method,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )


class TestPowerManagerEventPolicyEvaluationSeams:
    def test_get_keyboard_intent_state_returns_helper_result(self):
        from keyrgb.core.power.management.manager import PowerManager, safe_int_attr

        pm = PowerManager(MagicMock())

        with patch("keyrgb.core.power.management.manager.is_intentionally_off", return_value=True) as intent_state:
            assert pm._get_keyboard_intent_state() is True

        intent_state.assert_called_once_with(
            kb_controller=pm.kb_controller,
            config=pm._config,
            safe_int_attr_fn=safe_int_attr,
        )

    def test_get_keyboard_intent_state_logs_and_returns_none_on_runtime_error(self):
        from keyrgb.core.power.management.manager import PowerManager, logger

        pm = PowerManager(MagicMock())

        with (
            patch("keyrgb.core.power.management.manager.is_intentionally_off", side_effect=RuntimeError("boom")),
            patch.object(logger, "exception") as log_exception,
        ):
            assert pm._get_keyboard_intent_state() is None

        log_exception.assert_called_once_with("Power event intent-state evaluation failed")

    def test_get_keyboard_intent_state_propagates_unexpected_errors(self):
        from keyrgb.core.power.management.manager import PowerManager, logger

        pm = PowerManager(MagicMock())

        with (
            patch(
                "keyrgb.core.power.management.manager.is_intentionally_off",
                side_effect=AssertionError("unexpected intent bug"),
            ),
            patch.object(logger, "exception") as log_exception,
            pytest.raises(AssertionError, match="unexpected intent bug"),
        ):
            pm._get_keyboard_intent_state()

        log_exception.assert_not_called()

    def test_evaluate_power_event_policy_short_circuits_when_intent_state_is_unavailable(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock())
        policy_method = MagicMock()

        with patch.object(pm, "_get_keyboard_intent_state", return_value=None) as intent_state:
            assert (
                pm._evaluate_power_event_policy(
                    enabled=True,
                    action_enabled=True,
                    policy_method=policy_method,
                )
                is None
            )

        intent_state.assert_called_once_with()
        policy_method.assert_not_called()

    def test_evaluate_power_event_policy_logs_policy_failures_with_existing_message(self):
        from keyrgb.core.power.management.manager import PowerManager, logger

        pm = PowerManager(MagicMock())
        policy_method = MagicMock(side_effect=RuntimeError("policy boom"))

        with (
            patch.object(pm, "_get_keyboard_intent_state", return_value=False) as intent_state,
            patch.object(logger, "exception") as log_exception,
        ):
            assert (
                pm._evaluate_power_event_policy(
                    enabled=True,
                    action_enabled=True,
                    policy_method=policy_method,
                )
                is None
            )

        intent_state.assert_called_once_with()
        policy_method.assert_called_once()
        log_exception.assert_called_once_with("Power event policy evaluation failed")
