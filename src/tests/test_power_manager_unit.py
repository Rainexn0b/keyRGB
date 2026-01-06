#!/usr/bin/env python3
"""Unit tests for PowerManager (core/power_management/manager.py).

Tests power event handling, brightness policy, and config-gated behavior
without real hardware or blocking I/O.
"""

from __future__ import annotations

from types import SimpleNamespace
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
        from src.core.power_management.manager import PowerManager
        from src.core.config import Config

        mock_kb = MagicMock()
        del mock_kb.apply_brightness_from_power_policy
        mock_kb.engine = MagicMock()

        # Use a fresh config with explicit brightness
        cfg = Config()
        cfg.brightness = 50

        pm = PowerManager(mock_kb, config=cfg)
        pm._apply_brightness_policy(75)

        # Should call engine.set_brightness (config update may fail silently)
        mock_kb.engine.set_brightness.assert_called_once_with(75)

    def test_apply_brightness_handles_missing_engine_gracefully(self):
        """If engine is missing or raises, don't crash."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock(spec=[])  # no apply_brightness_from_power_policy, no engine

        pm = PowerManager(mock_kb)
        # Should not raise
        pm._apply_brightness_policy(60)

    def test_apply_brightness_ignores_negative_values(self):
        """Negative brightness is a no-op."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_kb.apply_brightness_from_power_policy = MagicMock()

        pm = PowerManager(mock_kb)
        pm._apply_brightness_policy(-10)

        mock_kb.apply_brightness_from_power_policy.assert_not_called()


class TestPowerManagerConfigGating:
    """Test that power management actions respect enable flags."""

    def test_is_enabled_returns_true_when_config_flag_is_true(self):
        """When power_management_enabled is True, _is_enabled returns True."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True

        assert pm._is_enabled() is True

    def test_is_enabled_returns_false_when_config_flag_is_false(self):
        """When power_management_enabled is False, _is_enabled returns False."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = False

        assert pm._is_enabled() is False

    def test_is_enabled_defaults_to_true_on_missing_attribute(self):
        """If config has no power_management_enabled attr, fail open (True)."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        mock_config = MagicMock()
        # Simulate missing attribute
        del mock_config.power_management_enabled
        mock_config.reload = MagicMock()

        pm = PowerManager(mock_kb, config=mock_config)
        # Should default to True
        assert pm._is_enabled() is True

    def test_is_enabled_defaults_to_true_on_reload_exception(self):
        """If config.reload() raises, _is_enabled fails open (True)."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.reload = MagicMock(side_effect=RuntimeError("boom"))

        assert pm._is_enabled() is True

    def test_flag_returns_default_on_reload_exception(self):
        """If config.reload() raises, _flag returns provided default."""
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.reload = MagicMock(side_effect=OSError("file gone"))

        assert pm._flag("some_flag", default=False) is False
        assert pm._flag("other_flag", default=True) is True


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
        # Transiently off (e.g., idle policy), but not user-forced off.
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

        # Ensure the policy saw 'not intentionally off' even though is_off was True.
        args, _kwargs = mock_policy_instance.handle_power_off_event.call_args
        inputs = args[0]
        assert inputs.is_off is False

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_suspend_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_suspend should call kb.turn_off() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_instance.handle_power_off_event.return_value = mock_result
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
        from src.core.power_management.manager import (
            PowerManager,
            RestoreFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_instance.handle_power_restore_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_restore_on_resume = True

        # Patch time.sleep to avoid delay in test
        with patch("time.sleep"):
            pm._on_resume()

        mock_kb.restore.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_lid_close_calls_turn_off_when_enabled(self, mock_policy_cls):
        """_on_lid_close should call kb.turn_off() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[TurnOffFromEvent()])
        mock_policy_instance.handle_power_off_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_off_on_lid_close = True

        pm._on_lid_close()

        mock_kb.turn_off.assert_called_once()

    @patch("src.core.power_management.manager.PowerEventPolicy")
    def test_on_lid_open_calls_restore_when_enabled(self, mock_policy_cls):
        """_on_lid_open should call kb.restore() when flags allow."""
        from src.core.power_management.manager import (
            PowerManager,
            RestoreFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = True
        mock_kb.restore = MagicMock()

        mock_policy_instance = MagicMock()
        mock_result = MagicMock(actions=[RestoreFromEvent()])
        mock_policy_instance.handle_power_restore_event.return_value = mock_result
        mock_policy_cls.return_value = mock_policy_instance

        pm = PowerManager(mock_kb)
        pm._config.power_management_enabled = True
        pm._config.power_restore_on_lid_open = True

        pm._on_lid_open()

        mock_kb.restore.assert_called_once()

    def test_handle_power_event_catches_exceptions_in_kb_methods(self):
        """If kb.turn_off/restore raises, _handle_power_event should not crash."""
        from src.core.power_management.manager import (
            PowerManager,
            TurnOffFromEvent,
        )

        mock_kb = MagicMock()
        mock_kb.is_off = False
        mock_kb.turn_off = MagicMock(side_effect=RuntimeError("hardware error"))

        with patch("src.core.power_management.manager.PowerEventPolicy") as mock_policy_cls:
            mock_policy_instance = MagicMock()
            mock_result = MagicMock(actions=[TurnOffFromEvent()])
            mock_policy_instance.handle_power_off_event.return_value = mock_result
            mock_policy_cls.return_value = mock_policy_instance

            pm = PowerManager(mock_kb)
            pm._config.power_management_enabled = True
            pm._config.power_off_on_suspend = True

            # Should not raise
            pm._on_suspend()


class TestPowerManagerMonitoringThreads:
    def test_start_monitoring_starts_two_daemon_threads(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)

        created = []

        def _fake_thread(*, target, daemon):
            t = MagicMock()
            t.target = target
            t.daemon = daemon
            created.append(t)
            return t

        with patch("src.core.power_management.manager.threading.Thread", side_effect=_fake_thread) as th:
            pm.start_monitoring()

        assert pm.monitoring is True
        assert th.call_count == 2
        assert created[0].daemon is True
        assert created[1].daemon is True
        created[0].start.assert_called_once()
        created[1].start.assert_called_once()

    def test_start_monitoring_is_noop_when_already_monitoring(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("src.core.power_management.manager.threading.Thread") as th:
            pm.start_monitoring()
        th.assert_not_called()

    def test_stop_monitoring_joins_threads_best_effort(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True
        pm.monitor_thread = MagicMock()
        pm._battery_thread = MagicMock()

        pm.stop_monitoring()

        assert pm.monitoring is False
        pm.monitor_thread.join.assert_called_once_with(timeout=2)
        pm._battery_thread.join.assert_called_once_with(timeout=2)


class TestPowerManagerMonitorLoopFallbacks:
    def test_monitor_loop_calls_monitor_prepare_for_sleep(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("src.core.power_management.manager.monitor_prepare_for_sleep") as mon:
            pm._monitor_loop()

        mon.assert_called_once()
        kwargs = mon.call_args.kwargs
        assert callable(kwargs["is_running"])
        assert callable(kwargs["on_started"])
        assert callable(kwargs["on_suspend"])
        assert callable(kwargs["on_resume"])

    def test_monitor_loop_falls_back_to_acpi_when_dbus_monitor_missing(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True
        pm._monitor_acpi_events = MagicMock()

        with (
            patch("src.core.power_management.manager.monitor_prepare_for_sleep", side_effect=FileNotFoundError),
            patch("src.core.power_management.manager.logger.warning") as warn,
        ):
            pm._monitor_loop()

        warn.assert_called_once()
        pm._monitor_acpi_events.assert_called_once()

    def test_monitor_loop_catches_unexpected_exceptions(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with (
            patch("src.core.power_management.manager.monitor_prepare_for_sleep", side_effect=RuntimeError("boom")),
            patch("src.core.power_management.manager.logger.exception") as exc,
        ):
            pm._monitor_loop()

        exc.assert_called_once()

    def test_start_lid_monitor_wires_callbacks(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("src.core.power_management.manager.start_sysfs_lid_monitoring") as start:
            pm._start_lid_monitor()

        start.assert_called_once()
        kwargs = start.call_args.kwargs
        assert callable(kwargs["is_running"])
        assert callable(kwargs["on_lid_close"])
        assert callable(kwargs["on_lid_open"])
        assert kwargs["logger"] is not None

    def test_monitor_acpi_events_wires_callbacks(self):
        from src.core.power_management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("src.core.power_management.manager.monitor_acpi_events") as mon:
            pm._monitor_acpi_events()

        mon.assert_called_once()
        kwargs = mon.call_args.kwargs
        assert callable(kwargs["is_running"])
        assert callable(kwargs["on_lid_close"])
        assert callable(kwargs["on_lid_open"])
        assert kwargs["logger"] is not None


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
        # Trigger current_brightness parse exception branch.
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

        # Policy result sequencing to cover: skip=True and action application.
        result_skip = SimpleNamespace(skip=True, actions=[])
        result_actions = SimpleNamespace(
            skip=False,
            actions=[TurnOffKeyboard(), RestoreKeyboard(), ApplyBrightness(brightness=42)],
        )
        fake_policy = MagicMock()
        fake_policy.update.side_effect = [result_skip, result_actions]

        # read_on_ac_power sequencing to cover:
        # - None branch
        # - power_management_enabled False branch
        # - skip branch
        # - actions branch
        on_ac_values = [None, True, True, True]

        sleep_calls = {"n": 0}

        def _sleep(_seconds):
            sleep_calls["n"] += 1
            # Flip config to disabled for the 2nd iteration only.
            if sleep_calls["n"] == 1:
                return
            if sleep_calls["n"] == 2:
                cfg.power_management_enabled = False
                return
            if sleep_calls["n"] == 3:
                cfg.power_management_enabled = True
                return
            # After the final sleep, stop.
            pm.monitoring = False

        with (
            patch("src.core.power_management.manager.read_on_ac_power", side_effect=on_ac_values),
            patch("src.core.power_management.manager.PowerSourceLoopPolicy", return_value=fake_policy),
            patch("src.core.power_management.manager.time.monotonic", return_value=123.0),
            patch("src.core.power_management.manager.time.sleep", side_effect=_sleep),
        ):
            pm._battery_saver_loop()

        # Only the actions iteration should invoke these.
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
            patch("src.core.power_management.manager.read_on_ac_power", side_effect=RuntimeError("boom")),
            patch("src.core.power_management.manager.time.sleep", side_effect=_sleep),
            patch("src.core.power_management.manager.logger.exception") as exc,
        ):
            pm._battery_saver_loop()

        exc.assert_called_once()


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
        from src.core.power_management.manager import PowerManager, RestoreFromEvent, TurnOffFromEvent

        mock_kb = MagicMock()
        mock_kb.turn_off = MagicMock()
        pm = PowerManager(mock_kb)
        pm._config.brightness = 50

        result = SimpleNamespace(actions=[RestoreFromEvent(), TurnOffFromEvent()])
        policy_method = MagicMock(return_value=result)

        # action_enabled False => should skip kb call entirely.
        pm._handle_power_event(
            enabled=True,
            action_enabled=False,
            log_message="x",
            policy_method=policy_method,
            expected_action_type=TurnOffFromEvent,
            kb_method_name="turn_off",
        )
        mock_kb.turn_off.assert_not_called()

        # action_enabled True => should run only matching action type.
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
        from src.core.power_management.manager import PowerEventInputs, PowerManager, TurnOffFromEvent

        captured = {}

        def _policy(inputs: PowerEventInputs):
            captured["inputs"] = inputs
            return SimpleNamespace(actions=[])

        # 1) user_forced_off True
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

        # 2) user_forced_off attribute errors => fall back to _user_forced_off
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

        # 3) config brightness == 0 => intentional off
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

        # Use a spec to avoid MagicMock auto-creating the optional hook attribute.
        mock_kb = MagicMock(spec=["engine"])
        mock_kb.engine = MagicMock()

        pm = PowerManager(mock_kb, config=_ConfigRaisingOnSet())
        pm._apply_brightness_policy(10)

        mock_kb.engine.set_brightness.assert_called_once_with(10)

    def test_apply_brightness_policy_logs_if_engine_set_brightness_raises(self):
        from src.core.power_management.manager import PowerManager

        # Use a spec to avoid MagicMock auto-creating the optional hook attribute.
        mock_kb = MagicMock(spec=["engine"])
        mock_kb.engine = MagicMock()
        mock_kb.engine.set_brightness = MagicMock(side_effect=RuntimeError("boom"))

        pm = PowerManager(mock_kb)

        with patch("src.core.power_management.manager.logger.exception") as exc:
            pm._apply_brightness_policy(10)

        exc.assert_called_once()
