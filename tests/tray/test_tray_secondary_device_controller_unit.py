from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


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