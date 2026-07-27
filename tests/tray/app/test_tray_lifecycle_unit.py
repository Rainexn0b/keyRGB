from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_start_power_monitoring_constructs_and_starts() -> None:
    from src.tray.app.lifecycle import start_power_monitoring

    tray = MagicMock()
    config = MagicMock()

    pm = MagicMock()
    power_manager_cls = MagicMock(return_value=pm)

    got = start_power_monitoring(tray, power_manager_cls=power_manager_cls, config=config)

    assert got is pm
    power_manager_cls.assert_called_once_with(tray, config=config)
    pm.start_monitoring.assert_called_once()


def test_start_power_monitoring_failure_rolls_back_partial_manager() -> None:
    import pytest

    from src.tray.app.lifecycle import start_power_monitoring

    pm = MagicMock()
    pm.start_monitoring.side_effect = RuntimeError("monitor startup")
    power_manager_cls = MagicMock(return_value=pm)

    with pytest.raises(RuntimeError, match="monitor startup"):
        start_power_monitoring(MagicMock(), power_manager_cls=power_manager_cls, config=MagicMock())

    pm.stop_monitoring.assert_called_once()


def test_start_all_polling_wires_pollers() -> None:
    from src.tray.app.lifecycle import start_all_polling

    tray = MagicMock()

    with (
        patch("src.tray.app.lifecycle.start_hardware_polling") as hw,
        patch("src.tray.app.lifecycle.start_config_polling") as cfg,
        patch("src.tray.app.lifecycle.start_icon_color_polling") as icon,
        patch("src.tray.app.lifecycle.start_idle_power_polling") as idle,
        patch("src.tray.app.lifecycle.start_time_scheduler_polling") as scheduler,
    ):
        start_all_polling(tray, ite_num_rows=6, ite_num_cols=21)

    hw.assert_called_once_with(tray)
    cfg.assert_called_once_with(tray, ite_num_rows=6, ite_num_cols=21)
    icon.assert_called_once_with(tray)
    idle.assert_called_once_with(tray, ite_num_rows=6, ite_num_cols=21)
    scheduler.assert_called_once_with(tray)


def test_shutdown_tray_runtime_stops_producers_before_engine_close(monkeypatch) -> None:
    from types import SimpleNamespace

    from src.tray.app import lifecycle

    calls: list[str] = []
    thread = SimpleNamespace(join=lambda *, timeout: calls.append(f"join:{timeout}"))
    event = SimpleNamespace(set=lambda: calls.append("pollers:set"))
    tray = SimpleNamespace(
        _polling_shutdown_event=event,
        _polling_threads=[thread],
        power_manager=SimpleNamespace(stop_monitoring=lambda: calls.append("power:stop")),
        engine=SimpleNamespace(close=lambda: calls.append("engine:close")),
    )
    monkeypatch.setattr(
        "src.tray.controllers.software_target_controller.close_secondary_software_target_cache",
        lambda _tray: calls.append("secondary:close"),
    )

    lifecycle.shutdown_tray_runtime_best_effort(tray)

    assert calls == ["pollers:set", "join:2.0", "power:stop", "engine:close", "secondary:close"]


def test_shutdown_tray_runtime_keeps_secondary_targets_open_if_engine_worker_is_stuck(monkeypatch) -> None:
    from types import SimpleNamespace

    from src.tray.app import lifecycle

    calls: list[str] = []
    tray = SimpleNamespace(
        _polling_threads=[],
        power_manager=None,
        engine=SimpleNamespace(
            close=lambda: calls.append("engine:close"),
            thread=SimpleNamespace(is_alive=lambda: True),
        ),
    )
    monkeypatch.setattr(
        "src.tray.controllers.software_target_controller.close_secondary_software_target_cache",
        lambda _tray: calls.append("secondary:close"),
    )

    lifecycle.shutdown_tray_runtime_best_effort(tray)

    assert calls == ["engine:close"]


def test_maybe_autostart_effect_calls_start_when_enabled_and_not_off() -> None:
    from src.tray.app.lifecycle import maybe_autostart_effect

    tray = MagicMock()
    tray.config = MagicMock(autostart=True)
    tray.is_off = False

    maybe_autostart_effect(tray)

    tray._start_current_effect.assert_called_once()


def test_maybe_autostart_effect_skips_when_off_or_disabled() -> None:
    from src.tray.app.lifecycle import maybe_autostart_effect

    tray = MagicMock()
    tray.config = MagicMock(autostart=True)
    tray.is_off = True

    maybe_autostart_effect(tray)
    tray._start_current_effect.assert_not_called()

    tray2 = MagicMock()
    tray2.config = MagicMock(autostart=False)
    tray2.is_off = False

    maybe_autostart_effect(tray2)
    tray2._start_current_effect.assert_not_called()
