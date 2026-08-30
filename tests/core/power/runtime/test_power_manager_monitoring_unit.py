"""Unit tests for PowerManager monitoring threads and monitor loop fallbacks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestPowerManagerMonitoringThreads:
    def test_start_monitoring_starts_two_daemon_threads(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)

        created = []

        def _fake_thread(*, target, daemon):
            t = MagicMock()
            t.target = target
            t.daemon = daemon
            created.append(t)
            return t

        with patch(
            "keyrgb.core.power.management.manager.threading.Thread",
            side_effect=_fake_thread,
        ) as th:
            pm.start_monitoring()

        assert pm.monitoring is True
        assert th.call_count == 2
        assert created[0].daemon is True
        assert created[1].daemon is True
        created[0].start.assert_called_once()
        created[1].start.assert_called_once()

    def test_start_monitoring_is_noop_when_already_monitoring(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("keyrgb.core.power.management.manager.threading.Thread") as th:
            pm.start_monitoring()
        th.assert_not_called()

    def test_prime_power_source_state_runs_one_iteration_without_sleep(self):
        from keyrgb.core.power.management.manager import PowerManager, PowerSourceLoopPolicy

        pm = PowerManager(MagicMock())
        pm._run_battery_saver_iteration = MagicMock(return_value=False)

        pm.prime_power_source_state()

        pm._run_battery_saver_iteration.assert_called_once()
        policy = pm._run_battery_saver_iteration.call_args.args[0]
        assert isinstance(policy, PowerSourceLoopPolicy)
        assert pm._run_battery_saver_iteration.call_args.kwargs == {"poll_interval_s": 0.0}

    def test_stop_monitoring_joins_threads_best_effort(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True
        pm.monitor_thread = MagicMock()
        pm._battery_thread = MagicMock()
        pm._lid_thread = MagicMock()
        pm.monitor_thread.is_alive.return_value = False
        pm._battery_thread.is_alive.return_value = False
        pm._lid_thread.is_alive.return_value = False
        process = MagicMock()
        pm._monitor_process = process

        quiesced = pm.stop_monitoring()

        assert pm.monitoring is False
        assert quiesced is True
        process.terminate.assert_called_once()
        pm.monitor_thread.join.assert_called_once_with(timeout=2)
        pm._lid_thread.join.assert_called_once_with(timeout=2)
        pm._battery_thread.join.assert_called_once_with(timeout=2)

    def test_stop_monitoring_reports_worker_still_alive_after_bounded_join(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock())
        pm.monitoring = True
        pm.monitor_thread = MagicMock()
        pm.monitor_thread.is_alive.return_value = False
        pm._lid_thread = MagicMock()
        pm._lid_thread.is_alive.return_value = True
        pm._battery_thread = MagicMock()
        pm._battery_thread.is_alive.return_value = False

        quiesced = pm.stop_monitoring()

        assert quiesced is False
        pm.monitor_thread.is_alive.assert_called_once_with()
        pm._lid_thread.is_alive.assert_called_once_with()
        pm._battery_thread.is_alive.assert_called_once_with()

    def test_stop_monitoring_continues_after_join_error_and_reports_not_quiesced(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock())
        pm.monitoring = True
        pm.monitor_thread = MagicMock()
        pm.monitor_thread.join.side_effect = RuntimeError("not started")
        pm._lid_thread = MagicMock()
        pm._lid_thread.is_alive.return_value = False
        pm._battery_thread = MagicMock()
        pm._battery_thread.is_alive.return_value = False

        quiesced = pm.stop_monitoring()

        assert quiesced is False
        pm._lid_thread.join.assert_called_once_with(timeout=2)
        pm._battery_thread.join.assert_called_once_with(timeout=2)

    def test_register_monitor_process_after_stop_terminates_it_immediately(self):
        from keyrgb.core.power.management.manager import PowerManager

        pm = PowerManager(MagicMock())
        process = MagicMock()

        pm._register_monitor_process(process)

        process.terminate.assert_called_once()


class TestPowerManagerMonitorLoopFallbacks:
    def test_monitor_loop_calls_monitor_prepare_for_sleep(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        def _mock_monitor(**kwargs):
            # Disable monitoring on the first run so the restart loop terminates
            # and we can assert the single invocation's wiring.
            pm.monitoring = False

        with patch(
            "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
            side_effect=_mock_monitor,
        ) as mon:
            pm._monitor_loop()

        mon.assert_called_once()
        kwargs = mon.call_args.kwargs
        assert callable(kwargs["is_running"])
        assert callable(kwargs["on_started"])
        assert callable(kwargs["on_suspend"])
        assert callable(kwargs["on_resume"])
        assert callable(kwargs["on_process_started"])
        assert callable(kwargs["on_process_stopped"])

    def test_monitor_loop_falls_back_to_acpi_when_dbus_monitor_missing(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True
        pm._monitor_acpi_events = MagicMock()

        with (
            patch(
                "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
                side_effect=FileNotFoundError,
            ),
            patch("keyrgb.core.power.management.manager.logger.warning") as warn,
        ):
            pm._monitor_loop()

        warn.assert_called_once()
        pm._monitor_acpi_events.assert_called_once()

    def test_monitor_loop_restarts_after_recoverable_callback_error(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        calls = {"n": 0}

        def _side_effect(**kwargs):
            # The real monitor invokes on_started once it spawns the process,
            # before any suspend/resume callbacks run.
            on_started = kwargs.get("on_started")
            if on_started is not None:
                on_started()
            calls["n"] += 1
            if calls["n"] == 1:
                # A recoverable runtime error from the suspend/resume callbacks
                # must not permanently end monitoring.
                raise RuntimeError("boom")
            # The restarted monitor ends cleanly by disabling monitoring.
            pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
                side_effect=_side_effect,
            ),
            patch(
                "keyrgb.core.power.management._monitor_runner._interruptible_sleep",
                return_value=None,
            ),
            patch("keyrgb.core.power.management.manager.logger.exception") as exc,
            patch.object(pm, "_start_lid_monitor"),
        ):
            pm._monitor_loop()

        assert calls["n"] == 2
        exc.assert_called_once()
        # The recoverable error is logged with a restart intent (lazy % formatting
        # means the delay is still a template token in call_args).
        assert any("restarting in" in str(c.args) for c in exc.call_args_list)

    def test_monitor_loop_restarts_after_eof_without_duplicate_lid_start(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        calls = {"n": 0}

        def _side_effect(**kwargs):
            # The real monitor invokes on_started once it spawns the process.
            on_started = kwargs.get("on_started")
            if on_started is not None:
                on_started()
            calls["n"] += 1
            if calls["n"] < 3:
                # dbus-monitor exits immediately (EOF / child exit).
                return
            pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
                side_effect=_side_effect,
            ),
            patch(
                "keyrgb.core.power.management._monitor_runner._interruptible_sleep",
                return_value=None,
            ),
            patch("keyrgb.core.power.management.manager.logger.warning") as warn,
            patch.object(pm, "_start_lid_monitor") as lid,
        ):
            pm._monitor_loop()

        assert calls["n"] == 3
        # Lid monitoring is owned by one thread; restarts must not duplicate it.
        lid.assert_called_once()
        assert sum(1 for c in warn.call_args_list if "restarting" in str(c.args)) >= 2

    def test_monitor_loop_stops_cleanly_without_restart_on_shutdown(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        calls = []

        def _side_effect(**kwargs):
            calls.append(1)
            # Monitoring disabled while the monitor runs: clean shutdown.
            pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
                side_effect=_side_effect,
            ),
            patch(
                "keyrgb.core.power.management._monitor_runner._interruptible_sleep",
                return_value=None,
            ) as sleep,
        ):
            pm._monitor_loop()

        assert len(calls) == 1
        # No restart backoff sleep on clean shutdown.
        sleep.assert_not_called()

    def test_monitor_loop_bounded_backoff_caps_at_max(self):
        from keyrgb.core.power.management._monitor_runner import (
            _MONITOR_RESTART_INITIAL_DELAY_S,
            _MONITOR_RESTART_MAX_DELAY_S,
        )
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        sleeps = []

        def _sleep(duration_s, is_running, *, interval_s=_MONITOR_RESTART_INITIAL_DELAY_S):
            sleeps.append(duration_s)
            if len(sleeps) >= 8:
                pm.monitoring = False

        with (
            patch(
                "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "keyrgb.core.power.management._monitor_runner._interruptible_sleep",
                side_effect=_sleep,
            ),
        ):
            pm._monitor_loop()

        assert sleeps
        assert sleeps[0] == _MONITOR_RESTART_INITIAL_DELAY_S
        # Backoff grows but never exceeds the cap even under repeated failure.
        assert max(sleeps) <= _MONITOR_RESTART_MAX_DELAY_S
        assert len({s for s in sleeps if s >= _MONITOR_RESTART_MAX_DELAY_S}) >= 1

    def test_monitor_loop_propagates_unexpected_exceptions(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with (
            patch(
                "keyrgb.core.power.management.manager.monitor_prepare_for_sleep",
                side_effect=AssertionError("unexpected monitor bug"),
            ),
            pytest.raises(AssertionError, match="unexpected monitor bug"),
        ):
            pm._monitor_loop()

    def test_start_lid_monitor_wires_callbacks(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("keyrgb.core.power.management.manager.start_sysfs_lid_monitoring") as start:
            lid_thread = start.return_value
            pm._start_lid_monitor()

        start.assert_called_once()
        kwargs = start.call_args.kwargs
        assert callable(kwargs["is_running"])
        assert callable(kwargs["on_lid_close"])
        assert callable(kwargs["on_lid_open"])
        assert kwargs["logger"] is not None
        assert pm._lid_thread is lid_thread

    def test_monitor_acpi_events_wires_callbacks(self):
        from keyrgb.core.power.management.manager import PowerManager

        mock_kb = MagicMock()
        pm = PowerManager(mock_kb)
        pm.monitoring = True

        with patch("keyrgb.core.power.management.manager.monitor_acpi_events") as mon:
            pm._monitor_acpi_events()

        mon.assert_called_once()
        kwargs = mon.call_args.kwargs
        assert callable(kwargs["is_running"])
        assert callable(kwargs["on_lid_close"])
        assert callable(kwargs["on_lid_open"])
        assert kwargs["logger"] is not None
        assert callable(kwargs["on_process_started"])
        assert callable(kwargs["on_process_stopped"])
