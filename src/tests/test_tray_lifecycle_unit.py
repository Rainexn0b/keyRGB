from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_start_power_monitoring_constructs_and_starts() -> None:
    from src.tray.lifecycle import start_power_monitoring

    tray = MagicMock()
    config = MagicMock()

    pm = MagicMock()
    power_manager_cls = MagicMock(return_value=pm)

    got = start_power_monitoring(tray, power_manager_cls=power_manager_cls, config=config)

    assert got is pm
    power_manager_cls.assert_called_once_with(tray, config=config)
    pm.start_monitoring.assert_called_once()


def test_start_all_polling_wires_pollers() -> None:
    from src.tray.lifecycle import start_all_polling

    tray = MagicMock()

    with (
        patch("src.tray.lifecycle.start_hardware_polling") as hw,
        patch("src.tray.lifecycle.start_config_polling") as cfg,
        patch("src.tray.lifecycle.start_icon_color_polling") as icon,
        patch("src.tray.lifecycle.start_idle_power_polling") as idle,
    ):
        start_all_polling(tray, ite_num_rows=6, ite_num_cols=21)

    hw.assert_called_once_with(tray)
    cfg.assert_called_once_with(tray, ite_num_rows=6, ite_num_cols=21)
    icon.assert_called_once_with(tray)
    idle.assert_called_once_with(tray, ite_num_rows=6, ite_num_cols=21)


def test_maybe_autostart_effect_calls_start_when_enabled_and_not_off() -> None:
    from src.tray.lifecycle import maybe_autostart_effect

    tray = MagicMock()
    tray.config = MagicMock(autostart=True)
    tray.is_off = False

    maybe_autostart_effect(tray)

    tray._start_current_effect.assert_called_once()


def test_maybe_autostart_effect_skips_when_off_or_disabled() -> None:
    from src.tray.lifecycle import maybe_autostart_effect

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
