"""Unit tests for PowerManager event handling and _handle_power_event branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestPowerManagerEventHandlers:
    """Test lid/suspend event handlers."""

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_suspend_records_intent_off_not_transient_is_off(self, mock_policy_cls):
        """Suspend should report user intent, not transient tray.is_off.

        If the keyboard is temporarily off due to idle/screen-off policy, we
        still want suspend/resume restore decisions to reflect user intent.
        """

        from src.core.power_management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb._user_forced_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_off_on_suspend = True
        pm._config.brightness = 25

        pm._on_suspend()

        args, _kwargs = mock_policy_instance.handle_power_off_event.call_args
        inputs = args[0]
        assert inputs.is_off is False

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_suspend_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_suspend should call kb.turn_off() when flags allow."""
        from src.core.power_management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
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
        from src.core.power_management.manager import PowerManager, RestoreFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_restore_on_resume = True

        with patch("time.sleep"):
            pm._on_resume()

        mock_kb.restore.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_lid_close_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_lid_close should call kb.turn_off() when flags allow."""
        from src.core.power_management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_off_on_lid_close = True

        pm._on_lid_close()

        mock_kb.turn_off.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_lid_open_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_lid_open should call kb.restore() when flags allow."""
        from src.core.power_management.manager import PowerManager, RestoreFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_restore_on_lid_open = True

        pm._on_lid_open()

        mock_kb.restore.assert_called_once()

    def test_handle_power_event_catches_exceptions_in_kb_methods(self):
        """If kb.turn_off/restore raises, _handle_power_event should not crash."""
        from src.core.power_management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=RuntimeError("hardware error"))

        with patch("src.core.power_management.manager.PowerEventPolicy") as mock_policy_cls:
            mock_policy_instance = MagicMock()
            mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
            mock_policy_cls.return_value = mock_policy_instance

            pm = PowerManager(mock_kb)
            pm._config.power_management_enabled = True
            pm._config.power_off_on_suspend = True

            pm._on_suspend()


class TestPowerManagerHandlePowerEventBranches:
    def test_handle_power_event_returns_when_policy_raises(self):
        from src.core.power_management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)

        pm._handle_power_event(
            enabled=True,
            action_enabled=True,
            log_message="x",
            policy_method=MagicMock(side_effect=RuntimeError("boom")),
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )

    def test_handle_power_event_filters_action_type_and_action_enabled(self):
        from src.core.power_management.manager import (
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
        from src.core.power_management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.brightness = 50

        result = SimpleNamespace(actions=[TurnOffFromEvent(), TurnOffFromEvent()])
        policy_method = MagicMock(return_value=result)

        with (
            patch("src.core.power_management.manager.time.sleep") as sleep,
            patch("src.core.power_management.manager.logger.info") as info,
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
        from src.core.power_management.manager import (
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
