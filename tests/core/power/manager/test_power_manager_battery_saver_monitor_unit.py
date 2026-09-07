"""Unit tests for PowerManager battery saver monitor loop."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest


class TestPowerManagerBatterySaverMonitor:
    def test_run_battery_saver_iteration_delegates_classification_then_execution(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock(), config=MagicMock())
        fake_policy = MagicMock()
        plan = object()
        coordinator = MagicMock()
        coordinator.classify.return_value = plan
        coordinator.execute.return_value = True
        pm._classify_battery_saver_iteration = coordinator.classify
        pm._execute_battery_saver_iteration_plan = coordinator.execute

        result = pm._run_battery_saver_iteration(fake_policy, poll_interval_s=2.0)

        assert result is True
        assert coordinator.mock_calls == [
            call.classify(fake_policy),
            call.execute(
                plan,
                poll_interval_s=2.0,
                record_power_mode_apply_result_fn=fake_policy.record_power_mode_apply_result,
            ),
        ]

    def test_run_battery_saver_iteration_preserves_apply_feedback_across_owner_thread(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.core.power.policies.power_source_loop_policy import ActivatePowerMode
        from keyrgb.core.power.system import PowerMode

        pm = PowerManager(MagicMock(), config=MagicMock())
        policy = MagicMock()
        plan = SimpleNamespace(should_sleep=False, actions=(ActivatePowerMode(PowerMode.PERFORMANCE),))
        pm._sync_lid_state_from_system = MagicMock()
        pm._keyboard_is_power_event_forced_off = MagicMock(return_value=False)
        pm._classify_battery_saver_iteration = MagicMock(return_value=plan)
        pm._activate_power_source_mode = MagicMock(return_value=True)
        caller_thread = threading.get_ident()

        def run_on_owner_thread(_tray, action):
            if threading.get_ident() != caller_thread:
                return action()
            result = []
            worker = threading.Thread(target=lambda: result.append(action()))
            worker.start()
            worker.join()
            return result[0]

        with patch.object(manager_module, "_run_tray_transition_if_available", side_effect=run_on_owner_thread):
            assert pm._run_battery_saver_iteration(policy, poll_interval_s=2.0) is False

        policy.record_power_mode_apply_result.assert_called_once_with(PowerMode.PERFORMANCE, True)

    def test_run_battery_saver_iteration_pauses_source_actions_while_lid_closed(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager

        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.power_off_on_lid_close = True
        pm = PowerManager(MagicMock(), config=cfg)
        pm._lid_closed = True
        pm._classify_battery_saver_iteration = MagicMock()
        pm._execute_battery_saver_iteration_plan = MagicMock()

        with (
            patch.object(manager_module, "read_lid_state", return_value="closed"),
            patch.object(manager_module.time, "sleep") as sleep,
        ):
            result = pm._run_battery_saver_iteration(MagicMock(), poll_interval_s=2.0)

        assert result is True
        sleep.assert_called_once_with(2.0)
        pm._classify_battery_saver_iteration.assert_not_called()
        pm._execute_battery_saver_iteration_plan.assert_not_called()

    def test_run_battery_saver_iteration_detects_closed_lid_and_pauses_source_actions(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb._power_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(power_forced_off=False)
        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.power_management_enabled = True
        cfg.power_off_on_lid_close = True
        cfg.brightness = 40
        pm = PowerManager(mock_kb, config=cfg)
        pm._classify_battery_saver_iteration = MagicMock()
        pm._execute_battery_saver_iteration_plan = MagicMock()

        with (
            patch.object(manager_module, "read_lid_state", return_value="closed"),
            patch.object(manager_module.time, "sleep") as sleep,
        ):
            result = pm._run_battery_saver_iteration(MagicMock(), poll_interval_s=2.0)

        assert result is True
        assert pm._lid_closed is True
        mock_kb.turn_off.assert_called_once()
        sleep.assert_called_once_with(2.0)
        pm._classify_battery_saver_iteration.assert_not_called()
        pm._execute_battery_saver_iteration_plan.assert_not_called()

    def test_run_battery_saver_iteration_pauses_source_actions_while_power_event_forced_off(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb._power_forced_off = True
        mock_kb.tray_idle_power_state = TrayIdlePowerState(power_forced_off=True)
        cfg = MagicMock()
        cfg.reload = MagicMock()
        pm = PowerManager(mock_kb, config=cfg)
        pm._classify_battery_saver_iteration = MagicMock()
        pm._execute_battery_saver_iteration_plan = MagicMock()

        with patch.object(manager_module.time, "sleep") as sleep:
            result = pm._run_battery_saver_iteration(MagicMock(), poll_interval_s=2.0)

        assert result is True
        sleep.assert_called_once_with(2.0)
        pm._classify_battery_saver_iteration.assert_not_called()
        pm._execute_battery_saver_iteration_plan.assert_not_called()

    def test_run_battery_saver_iteration_pauses_source_actions_for_bridge_power_forced_off_state(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.idle_power_state import TrayIdlePowerState

        mock_kb = MagicMock()
        mock_kb._power_forced_off = False
        mock_kb.tray_idle_power_state = TrayIdlePowerState(power_forced_off=True)
        pm = PowerManager(mock_kb, config=MagicMock())
        pm._classify_battery_saver_iteration = MagicMock()
        pm._execute_battery_saver_iteration_plan = MagicMock()

        with patch.object(manager_module.time, "sleep") as sleep:
            result = pm._run_battery_saver_iteration(MagicMock(), poll_interval_s=2.0)

        assert result is True
        sleep.assert_called_once_with(2.0)
        pm._classify_battery_saver_iteration.assert_not_called()
        pm._execute_battery_saver_iteration_plan.assert_not_called()

    def test_run_battery_saver_iteration_keeps_source_actions_when_lid_close_off_is_disabled(self):
        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager

        cfg = MagicMock()
        cfg.reload = MagicMock()
        cfg.power_off_on_lid_close = False
        pm = PowerManager(MagicMock(), config=cfg)
        pm._lid_closed = True
        fake_policy = MagicMock()
        plan = object()
        pm._classify_battery_saver_iteration = MagicMock(return_value=plan)
        pm._execute_battery_saver_iteration_plan = MagicMock(return_value=False)

        with patch.object(manager_module, "read_lid_state", return_value="closed"):
            result = pm._run_battery_saver_iteration(fake_policy, poll_interval_s=2.0)

        assert result is False
        pm._classify_battery_saver_iteration.assert_called_once_with(fake_policy)
        pm._execute_battery_saver_iteration_plan.assert_called_once_with(
            plan,
            poll_interval_s=2.0,
            record_power_mode_apply_result_fn=fake_policy.record_power_mode_apply_result,
        )

    def test_battery_saver_loop_logs_and_continues_on_exception(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        cfg = MagicMock()
        cfg.reload = MagicMock()

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        def _sleep(_seconds):
            pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.read_on_ac_power",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "keyrgb.core.power.management.manager.time.sleep",
                side_effect=_sleep,
            ),
            patch(
                "keyrgb.core.power.management.manager.logger.exception",
            ) as exc,
        ):
            pm._battery_saver_loop()

        exc.assert_called_once()

    def test_battery_saver_loop_propagates_unexpected_exceptions(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        cfg = MagicMock()
        cfg.reload = MagicMock()

        pm = PowerManager(mock_kb, config=cfg)
        pm.monitoring = True

        with (
            patch(
                "keyrgb.core.power.management.manager.read_on_ac_power",
                side_effect=AssertionError("unexpected battery loop bug"),
            ),
            pytest.raises(AssertionError, match="unexpected battery loop bug"),
        ):
            pm._battery_saver_loop()

    def test_power_source_iteration_cannot_finish_after_newer_serialized_transition(self):
        import threading
        import time

        from keyrgb.core.power.management import manager as manager_module
        from keyrgb.core.power.management.manager import PowerManager
        from keyrgb.tray.controllers.runtime_coordination import run_tray_transition
        from keyrgb.tray.controllers.runtime_coordinator import TrayRuntimeCoordinator

        class _Tray:
            def __init__(self) -> None:
                self.runtime_coordinator = TrayRuntimeCoordinator()
                self.is_off = True

            def run_runtime_transition(self, action):
                return run_tray_transition(self, action)

        tray = _Tray()
        pm = PowerManager(tray, config=MagicMock())
        iteration_started = threading.Event()
        release_iteration = threading.Event()

        def run_iteration(*_args, **_kwargs) -> bool:
            iteration_started.set()
            release_iteration.wait()
            tray.is_off = False
            return False

        iteration = threading.Thread(target=lambda: pm._run_battery_saver_iteration(MagicMock(), poll_interval_s=0.0))
        manual_off = threading.Thread(
            target=lambda: run_tray_transition(tray, lambda: setattr(tray, "is_off", True)),
        )

        try:
            with patch.object(manager_module._battery_saver, "run_battery_saver_iteration", side_effect=run_iteration):
                iteration.start()
                assert iteration_started.wait(timeout=1.0)
                manual_off.start()
                deadline = time.monotonic() + 1.0
                while tray.runtime_coordinator.capture_revision() < 2 and time.monotonic() < deadline:
                    threading.Event().wait(0.001)
                assert tray.runtime_coordinator.capture_revision() >= 2
                release_iteration.set()
                iteration.join(timeout=1.0)
                manual_off.join(timeout=1.0)
        finally:
            release_iteration.set()
            assert tray.runtime_coordinator.stop_and_drain(timeout_s=1.0) is True

        assert not iteration.is_alive()
        assert not manual_off.is_alive()
        assert tray.is_off is True
