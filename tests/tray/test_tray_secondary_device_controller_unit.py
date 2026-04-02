from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call


def _make_tray() -> SimpleNamespace:
    return SimpleNamespace(
        selected_device_context="lightbar:048d:7001",
        config=SimpleNamespace(lightbar_brightness=25),
        _update_menu=MagicMock(),
        _log_exception=MagicMock(),
        _notify_permission_issue=MagicMock(),
        _log_event=MagicMock(),
    )


def test_apply_selected_secondary_brightness_updates_lightbar_device(monkeypatch) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    tray = _make_tray()
    seen: list[int] = []

    class DummyDevice:
        def set_brightness(self, brightness: int) -> None:
            seen.append(int(brightness))

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: DummyDevice(),
    )

    assert apply_selected_secondary_brightness(tray, "6") is True
    assert tray.config.lightbar_brightness == 30
    assert seen == [30]
    tray._update_menu.assert_called_once()


def test_turn_off_selected_secondary_device_turns_off_lightbar(monkeypatch) -> None:
    from src.tray.controllers.secondary_device_controller import turn_off_selected_secondary_device

    tray = _make_tray()
    calls = {"off": 0}

    class DummyDevice:
        def turn_off(self) -> None:
            calls["off"] += 1

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: DummyDevice(),
    )

    assert turn_off_selected_secondary_device(tray) is True
    assert tray.config.lightbar_brightness == 0
    assert calls == {"off": 1}
    tray._update_menu.assert_called_once()


def test_apply_selected_secondary_brightness_notifies_permission_errors(monkeypatch) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    tray = _make_tray()
    err = PermissionError("denied")

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: (_ for _ in ()).throw(err),
    )

    assert apply_selected_secondary_brightness(tray, "4") is False
    tray._notify_permission_issue.assert_called_once_with(err)


def test_apply_selected_secondary_brightness_logs_recoverable_config_write_errors(monkeypatch) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    class DummyConfig:
        @property
        def lightbar_brightness(self) -> int:
            return 25

        @lightbar_brightness.setter
        def lightbar_brightness(self, value: object) -> None:
            raise ValueError("bad brightness")

    tray = _make_tray()
    tray.config = DummyConfig()
    seen: list[int] = []

    class DummyDevice:
        def set_brightness(self, brightness: int) -> None:
            seen.append(int(brightness))

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: DummyDevice(),
    )

    assert apply_selected_secondary_brightness(tray, "4") is True
    assert seen == [20]
    tray._log_exception.assert_called_once()
    msg, exc = tray._log_exception.call_args.args
    assert msg == "Failed to store lightbar brightness: %s"
    assert isinstance(exc, ValueError)
    tray._update_menu.assert_called_once()


def test_apply_selected_secondary_brightness_logs_notify_callback_failures(monkeypatch) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    tray = _make_tray()
    err = PermissionError("denied")
    notify_err = RuntimeError("notify failed")
    tray._notify_permission_issue.side_effect = notify_err

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: (_ for _ in ()).throw(err),
    )

    assert apply_selected_secondary_brightness(tray, "4") is False
    tray._notify_permission_issue.assert_called_once_with(err)
    assert tray._log_exception.call_args_list == [
        call("Failed to notify lightbar permission issue: %s", notify_err),
        call("Error applying lightbar brightness: %s", err),
    ]


def test_apply_selected_secondary_brightness_logs_menu_refresh_failures(monkeypatch) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    tray = _make_tray()
    menu_err = RuntimeError("menu failed")
    tray._update_menu.side_effect = menu_err
    seen: list[int] = []

    class DummyDevice:
        def set_brightness(self, brightness: int) -> None:
            seen.append(int(brightness))

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: DummyDevice(),
    )

    assert apply_selected_secondary_brightness(tray, "6") is True
    assert seen == [30]
    tray._log_exception.assert_called_once_with("Failed to refresh tray menu after lightbar action: %s", menu_err)


def test_apply_selected_secondary_brightness_falls_back_to_module_logging_when_tray_logger_fails(monkeypatch) -> None:
    from src.tray.controllers import secondary_device_controller as controller

    tray = _make_tray()
    logger_err = RuntimeError("logger failed")
    menu_err = RuntimeError("menu failed")
    tray._log_exception.side_effect = logger_err
    tray._update_menu.side_effect = menu_err
    module_error = MagicMock()
    module_exception = MagicMock()

    class DummyDevice:
        def set_brightness(self, brightness: int) -> None:
            return None

    monkeypatch.setattr(controller.logger, "error", module_error)
    monkeypatch.setattr(controller.logger, "exception", module_exception)
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.Ite8233Backend.get_device",
        lambda self: DummyDevice(),
    )

    assert controller.apply_selected_secondary_brightness(tray, "6") is True
    tray._log_exception.assert_called_once_with("Failed to refresh tray menu after lightbar action: %s", menu_err)
    module_exception.assert_called_once_with(
        "Tray exception logger failed while logging secondary device boundary: %s",
        logger_err,
    )
    module_error.assert_called_once()
    assert module_error.call_args.args == ("Failed to refresh tray menu after lightbar action: %s", menu_err)
    assert module_error.call_args.kwargs["exc_info"] == (type(menu_err), menu_err, menu_err.__traceback__)