from __future__ import annotations

from types import SimpleNamespace

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


class _EnsureFailure(Exception):
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
