"""Unit tests for PowerManager event handling and _handle_power_event branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class TestPowerManagerEventHandlers:
    """Test lid/suspend event handlers."""

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_suspend_records_intent_off_not_transient_is_off(self, mock_policy_cls):
        """Suspend should report user intent, not transient tray.is_off.

        If the keyboard is temporarily off due to idle/screen-off policy, we
        still want suspend/resume restore decisions to reflect user intent.
        """

        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb._user_forced_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True
        pm._config.brightness = 25

        pm._on_suspend()

        args, _kwargs = mock_policy_instance.handle_power_off_event.call_args
        inputs = args[0]
        assert inputs.is_off is False

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_suspend should call kb.turn_off() when flags allow."""
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_suspend = True

        pm._on_suspend()

        mock_kb.turn_off.assert_called_once()

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_defaults_to_enabled_when_config_reload_raises_runtime_error(self, mock_policy_cls):
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        class _ConfigBrokenReload:
            def reload(self):
                raise RuntimeError("reload failed")

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        with patch("src.core.power.management.manager.logger.exception") as exc:
            pm = PowerManager(mock_kb, config=_ConfigBrokenReload())
            pm._on_suspend()

        mock_kb.turn_off.assert_called_once()
        assert exc.call_count == 2

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_defaults_to_enabled_when_management_flag_read_raises_runtime_error(self, mock_policy_cls):
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        class _ConfigBrokenFlagRead:
            def reload(self):
                return None

            @property
            def management_enabled(self):
                raise RuntimeError("flag failed")

            power_off_on_suspend = True

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        with patch("src.core.power.management.manager.logger.exception") as exc:
            pm = PowerManager(mock_kb, config=_ConfigBrokenFlagRead())
            pm._on_suspend()

        mock_kb.turn_off.assert_called_once()
        exc.assert_called_once_with("Failed to read power management config flag '%s'", "management_enabled")

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_skips_when_disabled(self, mock_policy_cls):
        """_on_suspend should not call turn_off when power_management_enabled=False."""
        from src.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = False

        pm._on_suspend()

        mock_kb.turn_off.assert_not_called()

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_resume_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_resume should call kb.restore() when flags allow."""
        from src.core.power.management.manager import PowerManager, RestoreFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_restore_on_resume = True

        with patch("time.sleep"):
            pm._on_resume()

        mock_kb.restore.assert_called_once()

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_lid_close_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_lid_close should call kb.turn_off() when flags allow."""
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_lid_close = True

        pm._on_lid_close()

        mock_kb.turn_off.assert_called_once()

    @patch("src.core.power.management.manager.PowerEventPolicy")
    def test_on_lid_open_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_lid_open should call kb.restore() when flags allow."""
        from src.core.power.management.manager import PowerManager, RestoreFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_restore_on_lid_open = True

        pm._on_lid_open()

        mock_kb.restore.assert_called_once()

    def test_handle_power_event_catches_exceptions_in_kb_methods(self):
        """If kb.turn_off/restore raises, _handle_power_event should not crash."""
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=RuntimeError("hardware error"))

        with (
            patch("src.core.power.management.manager.PowerEventPolicy") as mock_policy_cls,
            patch("src.core.power.management.manager.logger.exception") as exc,
        ):
            mock_policy_instance = MagicMock()
            mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
            mock_policy_cls.return_value = mock_policy_instance

            pm = PowerManager(mock_kb)
            pm._config.management_enabled = True
            pm._config.power_off_on_suspend = True

            pm._on_suspend()

        exc.assert_called_once()

    def test_handle_power_event_propagates_unexpected_keyboard_method_errors(self):
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=AssertionError("unexpected keyboard bug"))

        with patch("src.core.power.management.manager.PowerEventPolicy") as mock_policy_cls:
            mock_policy_instance = MagicMock()
            mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
            mock_policy_cls.return_value = mock_policy_instance

            pm = PowerManager(mock_kb)
            pm._config.management_enabled = True
            pm._config.power_off_on_suspend = True

            with pytest.raises(AssertionError, match="unexpected keyboard bug"):
                pm._on_suspend()


class TestPowerManagerEventHandlerRoutingSeams:
    def test_on_suspend_delegates_suspend_route_metadata_to_shared_helper(self):
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

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
        from src.core.power.management.manager import PowerManager, RestoreFromEvent

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
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

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
        from src.core.power.management.manager import PowerManager, RestoreFromEvent

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
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

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
        from src.core.power.management.manager import PowerManager, safe_int_attr

        pm = PowerManager(MagicMock())

        with patch("src.core.power.management.manager.is_intentionally_off", return_value=True) as intent_state:
            assert pm._get_keyboard_intent_state() is True

        intent_state.assert_called_once_with(
            kb_controller=pm.kb_controller,
            config=pm._config,
            safe_int_attr_fn=safe_int_attr,
        )

    def test_get_keyboard_intent_state_logs_and_returns_none_on_runtime_error(self):
        from src.core.power.management.manager import PowerManager, logger

        pm = PowerManager(MagicMock())

        with (
            patch("src.core.power.management.manager.is_intentionally_off", side_effect=RuntimeError("boom")),
            patch.object(logger, "exception") as log_exception,
        ):
            assert pm._get_keyboard_intent_state() is None

        log_exception.assert_called_once_with("Power event intent-state evaluation failed")

    def test_get_keyboard_intent_state_propagates_unexpected_errors(self):
        from src.core.power.management.manager import PowerManager, logger

        pm = PowerManager(MagicMock())

        with (
            patch(
                "src.core.power.management.manager.is_intentionally_off",
                side_effect=AssertionError("unexpected intent bug"),
            ),
            patch.object(logger, "exception") as log_exception,
        ):
            with pytest.raises(AssertionError, match="unexpected intent bug"):
                pm._get_keyboard_intent_state()

        log_exception.assert_not_called()

    def test_evaluate_power_event_policy_short_circuits_when_intent_state_is_unavailable(self):
        from src.core.power.management.manager import PowerManager

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
        from src.core.power.management.manager import PowerManager, logger

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


class TestPowerManagerHandlePowerEventBranches:
    def test_handle_power_event_returns_when_policy_raises(self):
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)

        with patch("src.core.power.management.manager.logger.exception") as exc:
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
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

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
        from src.core.power.management.manager import (
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
        from src.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.brightness = 50

        result = SimpleNamespace(actions=[TurnOffFromEvent(), TurnOffFromEvent()])
        policy_method = MagicMock(return_value=result)

        with (
            patch("src.core.power.management.manager.time.sleep") as sleep,
            patch("src.core.power.management.manager.logger.info") as info,
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
        from src.core.power.management.manager import (
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

        kb3 = MagicMock()
        kb3.user_forced_off = False
        kb3._user_forced_off = False
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
