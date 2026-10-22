"""Unit tests for PowerManager event handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPowerManagerEventHandlers:
    """Test lid/suspend event handlers."""

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_suspend_records_intent_off_not_transient_is_off(self, mock_policy_cls):
        """Suspend should report user intent, not transient tray.is_off.

        If the keyboard is temporarily off due to idle/screen-off policy, we
        still want suspend/resume restore decisions to reflect user intent.
        """

        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb._user_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(user_forced_off=False)
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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_suspend should call kb.turn_off() when flags allow."""
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_defaults_to_enabled_when_config_reload_raises_runtime_error(self, mock_policy_cls):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        class _ConfigBrokenReload:
            def reload(self):
                raise RuntimeError("reload failed")

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        with patch("keyrgb.core.power.management.manager.logger.exception") as exc:
            pm = PowerManager(mock_kb, config=_ConfigBrokenReload())
            pm._on_suspend()

        mock_kb.turn_off.assert_called_once()
        assert exc.call_count == 2

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_defaults_to_enabled_when_management_flag_read_raises_runtime_error(self, mock_policy_cls):
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

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

        with patch("keyrgb.core.power.management.manager.logger.exception") as exc:
            pm = PowerManager(mock_kb, config=_ConfigBrokenFlagRead())
            pm._on_suspend()

        mock_kb.turn_off.assert_called_once()
        exc.assert_called_once_with("Failed to read power management config flag '%s'", "management_enabled")

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_suspend_skips_when_disabled(self, mock_policy_cls):
        """_on_suspend should not call turn_off when power_management_enabled=False."""
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = False

        pm._on_suspend()

        mock_kb.turn_off.assert_not_called()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_resume_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_resume should call kb.restore() when flags allow."""
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent

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

        mock_kb.restore.assert_not_called()
        mock_policy_instance.restore_pending = True
        pm._power_event_clock = lambda: pm._pending_power_restore_not_before
        pm._retry_pending_power_restore()

        mock_kb.restore.assert_called_once()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_lid_close_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_lid_close should call kb.turn_off() when flags allow."""
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_on_lid_open_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_lid_open should call kb.restore() when flags allow."""
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent

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

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_lid_handlers_track_lid_closed_state(self, mock_policy_cls):
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_off_on_lid_close = True
        pm._config.power_restore_on_lid_open = True

        pm._on_lid_close()
        assert pm._lid_closed is True

        pm._on_lid_open()
        assert pm._lid_closed is False

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_delayed_resume_is_discarded_after_newer_suspend(self, mock_policy_cls):
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent, TurnOffFromEvent
        from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

        mock_kb = MagicMock()
        mock_kb.is_off = False
        coordinator = TrayRuntimeCoordinator()
        mock_kb.run_runtime_transition = coordinator.run
        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.management_enabled = True
        pm._config.power_restore_on_resume = True
        pm._config.power_off_on_suspend = True
        try:
            pm._power_event_clock = lambda: 100.0
            pm._on_resume()
            pm._on_suspend()
            pm._power_event_clock = lambda: 101.0
            coordinator.run(pm._retry_pending_power_restore)
        finally:
            assert coordinator.stop_and_drain(timeout_s=1.0) is True

        mock_kb.turn_off.assert_called_once_with()
        mock_kb.restore.assert_not_called()

    def test_duplicate_lid_open_retries_restore_discarded_as_stale(self):
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

        mock_kb = MagicMock()
        coordinator = TrayRuntimeCoordinator()
        mock_kb.run_runtime_transition = coordinator.run
        mock_kb.turn_off = MagicMock(return_value=True)
        mock_kb.restore = MagicMock(return_value=True)
        pm = PowerManager(mock_kb, config=MagicMock())
        pm._is_enabled = MagicMock(return_value=True)
        pm._flag = MagicMock(return_value=True)
        pm._get_keyboard_intent_state = MagicMock(return_value=False)
        pm._lid_closed = True

        # Save the original lit intent and perform the suspend-side off first.
        pm._on_suspend()
        mock_kb.turn_off.assert_called_once_with()

        try:
            pm._power_event_clock = lambda: 100.0
            pm._on_resume()
            pm._on_lid_open()
            mock_kb.restore.assert_not_called()
            pm._power_event_clock = lambda: 101.0
            coordinator.run(pm._retry_pending_power_restore)
        finally:
            assert coordinator.stop_and_drain(timeout_s=1.0) is True

        mock_kb.restore.assert_called_once_with()

    @patch("keyrgb.core.power.management.manager.PowerEventPolicy")
    def test_delayed_resume_is_discarded_after_newer_manual_transition(self, mock_policy_cls):
        from keyrgb.core.power.management.manager import PowerManager, RestoreFromEvent
        from keyrgb.tray.controllers.runtime_coordination import (
            run_tray_transition,
        )
        from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        class _Tray:
            is_off = False
            _user_forced_off = False

            def __init__(self) -> None:
                self.runtime_coordinator = TrayRuntimeCoordinator()
                self.tray_idle_power_state = TrayIdlePowerState()
                self.turn_off = MagicMock()
                self.restore = MagicMock()

            def run_runtime_transition(self, action):
                return run_tray_transition(self, action)

            def capture_lighting_intent_revision(self):
                return self.runtime_coordinator.capture_intent_revision()

            def active_lighting_intent_revision(self):
                return self.runtime_coordinator.active_intent_revision()

        tray = _Tray()
        mock_policy_instance = MagicMock()
        mock_policy_instance.handle_power_restore_event.return_value = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_cls.return_value = mock_policy_instance
        pm = PowerManager(tray)
        pm._config.management_enabled = True
        pm._config.power_restore_on_resume = True
        try:
            pm._power_event_clock = lambda: 100.0
            pm._on_resume()
            run_tray_transition(tray, tray.turn_off, supersedes_lighting=True)
            mock_policy_instance.restore_pending = True
            pm._power_event_clock = lambda: 101.0
            tray.run_runtime_transition(pm._retry_pending_power_restore)
        finally:
            assert tray.runtime_coordinator.stop_and_drain(timeout_s=1.0) is True

        tray.restore.assert_not_called()
        tray.turn_off.assert_called_once_with()

    def test_handle_power_event_catches_exceptions_in_kb_methods(self):
        """If kb.turn_off/restore raises, _handle_power_event should not crash."""
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=RuntimeError("hardware error"))

        with (
            patch("keyrgb.core.power.management.manager.PowerEventPolicy") as mock_policy_cls,
            patch("keyrgb.core.power.management.manager.logger.exception") as exc,
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
        from keyrgb.core.power.management.manager import PowerManager, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=AssertionError("unexpected keyboard bug"))

        with patch("keyrgb.core.power.management.manager.PowerEventPolicy") as mock_policy_cls:
            mock_policy_instance = MagicMock()
            mock_policy_instance.handle_power_off_event.return_value = MagicMock(actions=[TurnOffFromEvent()])
            mock_policy_cls.return_value = mock_policy_instance

            pm = PowerManager(mock_kb)
            pm._config.management_enabled = True
            pm._config.power_off_on_suspend = True

            with pytest.raises(AssertionError, match="unexpected keyboard bug"):
                pm._on_suspend()
