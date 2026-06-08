from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tray.ui import _menu_status_devices, menu_status


def _keyboard_only_entries(entries: list[dict]) -> list[dict]:
    return [e for e in entries if e.get("device_type") == "keyboard"]


def _virtual_entries(entries: list[dict]) -> list[dict]:
    return [e for e in entries if e.get("device_type") in {"logo", "neon", "vent"}]


def test_device_context_entries_include_virtual_routes_when_parent_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_menu_status_devices, "_parent_backend_is_available", lambda _route: True)

    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
    )

    entries = menu_status.device_context_entries(tray)

    virtual = _virtual_entries(entries)
    assert len(virtual) == 3
    assert {e["device_type"] for e in virtual} == {"logo", "neon", "vent"}
    assert {e["backend_name"] for e in virtual} == {
        "ite8258-chassis-logo",
        "ite8258-chassis-neon",
        "ite8258-chassis-vent",
    }
    assert {e["key"] for e in virtual} == {
        "ite8258-chassis-logo",
        "ite8258-chassis-neon",
        "ite8258-chassis-vent",
    }
    assert {e["status"] for e in virtual} == {"supported"}


def test_device_context_entries_exclude_virtual_routes_when_parent_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_menu_status_devices, "_parent_backend_is_available", lambda _route: False)

    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
    )

    entries = menu_status.device_context_entries(tray)

    assert _virtual_entries(entries) == []
    assert len(_keyboard_only_entries(entries)) == 1


def test_virtual_route_text_uses_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_menu_status_devices, "_parent_backend_is_available", lambda _route: True)

    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
    )

    entries = menu_status.device_context_entries(tray)
    texts = {e["device_type"]: e["text"] for e in entries if e.get("device_type") in {"logo", "neon", "vent"}}

    assert texts == {"logo": "Logo", "neon": "Neon Strip", "vent": "Vents"}


def test_parent_backend_is_available_returns_false_on_backend_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenBackend:
        @property
        def is_available(self) -> bool:
            raise RuntimeError("probe failed")

    route = SimpleNamespace(get_backend=lambda: _BrokenBackend())

    assert _menu_status_devices._parent_backend_is_available(route) is False  # type: ignore[arg-type]


def test_parent_backend_is_available_returns_backend_availability() -> None:
    route = SimpleNamespace(get_backend=lambda: SimpleNamespace(is_available=lambda: True))

    assert _menu_status_devices._parent_backend_is_available(route) is True  # type: ignore[arg-type]
