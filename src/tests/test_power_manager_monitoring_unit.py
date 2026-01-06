"""Unit tests for PowerManager monitoring threads and monitor loop fallbacks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


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

        with patch(
            "src.core.power_management.manager.threading.Thread",
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
            patch(
                "src.core.power_management.manager.monitor_prepare_for_sleep",
                side_effect=FileNotFoundError,
            ),
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
            patch(
                "src.core.power_management.manager.monitor_prepare_for_sleep",
                side_effect=RuntimeError("boom"),
            ),
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
