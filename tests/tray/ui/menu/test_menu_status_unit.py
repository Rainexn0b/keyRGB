from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tray.ui import menu_status


class _BlockedSelectedDeviceContextTray:
    def __init__(self) -> None:
        self._selected_device_context = "missing:device"
        self.config = _BlockedTrayConfig()

    @property
    def selected_device_context(self) -> str:
        return self._selected_device_context

    @selected_device_context.setter
    def selected_device_context(self, _value: str) -> None:
        raise AttributeError("selected context is read-only")


class _BlockedTrayConfig:
    @property
    def tray_device_context(self) -> str:
        return "missing:device"

    @tray_device_context.setter
    def tray_device_context(self, _value: str) -> None:
        raise AttributeError("tray device context is read-only")


class _BrokenPerKeyColors:
    def __len__(self) -> int:
        raise LookupError("broken per-key color container")


class _UnexpectedBrokenPerKeyColors:
    def __len__(self) -> int:
        raise AssertionError("unexpected per-key status bug")


class _EnsureFailure(RuntimeError):
    pass


class _UnexpectedEnsureFailure(AssertionError):
    pass


def test_selected_device_context_key_returns_fallback_when_context_sync_attrs_are_blocked() -> None:
    tray = _BlockedSelectedDeviceContextTray()

    selected = menu_status.selected_device_context_key(
        tray,
        entries=[{"key": "keyboard", "device_type": "keyboard", "status": "supported", "text": "Keyboard"}],
    )

    assert selected == "keyboard"


def test_is_software_mode_logs_and_falls_back_when_per_key_length_is_broken(monkeypatch) -> None:
    logged: list[tuple[str, str, Exception]] = []

    monkeypatch.setattr(
        menu_status,
        "_log_menu_debug",
        lambda key, msg, exc, *, interval_s=60: logged.append((key, msg, exc)),
    )

    tray = SimpleNamespace(
        config=SimpleNamespace(effect="none", per_key_colors=_BrokenPerKeyColors()),
        backend=None,
    )

    assert menu_status.is_software_mode(tray) is False
    assert len(logged) == 1
    assert logged[0][0] == "tray.menu.per_key_colors"
    assert "per-key colors" in logged[0][1].lower()
    assert isinstance(logged[0][2], LookupError)


def test_is_software_mode_propagates_unexpected_per_key_length_errors() -> None:
    tray = SimpleNamespace(
        config=SimpleNamespace(effect="none", per_key_colors=_UnexpectedBrokenPerKeyColors()),
        backend=None,
    )

    with pytest.raises(AssertionError, match="unexpected per-key status bug"):
        menu_status.is_software_mode(tray)


def test_probe_device_available_logs_and_preserves_engine_state_when_ensure_raises(monkeypatch) -> None:
    logged: list[tuple[str, str, Exception]] = []

    monkeypatch.setattr(
        menu_status,
        "_log_menu_debug",
        lambda key, msg, exc, *, interval_s=60: logged.append((key, msg, exc)),
    )

    engine = SimpleNamespace(
        device_available=False,
        _ensure_device_available=lambda: (_ for _ in ()).throw(_EnsureFailure("boom")),
    )
    tray = SimpleNamespace(engine=engine)

    assert menu_status.probe_device_available(tray) is False
    assert len(logged) == 1
    assert logged[0][0] == "tray.menu.ensure_device"
    assert "device availability" in logged[0][1].lower()
    assert isinstance(logged[0][2], _EnsureFailure)


def test_probe_device_available_propagates_unexpected_ensure_errors() -> None:
    engine = SimpleNamespace(
        device_available=False,
        _ensure_device_available=lambda: (_ for _ in ()).throw(_UnexpectedEnsureFailure("unexpected ensure bug")),
    )
    tray = SimpleNamespace(engine=engine)

    with pytest.raises(_UnexpectedEnsureFailure, match="unexpected ensure bug"):
        menu_status.probe_device_available(tray)


def test_keyboard_status_text_uses_ite8291r3_backend_display_name(monkeypatch) -> None:
    monkeypatch.setattr(menu_status, "probe_device_available", lambda tray: True)

    tray = SimpleNamespace(
        backend=SimpleNamespace(name="ite8291r3"),
        backend_probe=SimpleNamespace(identifiers={"usb_vid": "0x048d", "usb_pid": "0x600b"}),
    )

    assert menu_status.keyboard_status_text(tray) == "Keyboard: ITE 8291r3 (USB) (048d:600b)"


def test_device_context_entries_threads_backend_name_from_candidate_probe_names() -> None:
    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={
            "candidates": [
                {
                    "device_type": "lightbar",
                    "product": "ITE Device(8233)",
                    "usb_vid": "0x048d",
                    "usb_pid": "0x7001",
                    "status": "supported",
                    "probe_names": ["ite8233"],
                }
            ]
        },
    )

    entries = menu_status.device_context_entries(tray)

    assert entries[1]["device_type"] == "lightbar"
    assert entries[1]["backend_name"] == "ite8233"


def test_device_context_entries_use_sysfs_mouse_context_key_and_backend_name() -> None:
    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={
            "candidates": [
                {
                    "device_type": "mouse",
                    "product": "usbmouse::rgb",
                    "status": "supported",
                    "context_key": "mouse:sysfs:usbmouse__rgb",
                    "probe_names": ["sysfs-mouse"],
                }
            ]
        },
    )

    entries = menu_status.device_context_entries(tray)

    assert entries[1]["key"] == "mouse:sysfs:usbmouse__rgb"
    assert entries[1]["backend_name"] == "sysfs-mouse"
    assert entries[1]["text"] == "Mouse: usbmouse::rgb"
