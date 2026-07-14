from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.core.secondary_device_routes import iter_virtual_routes
from src.tray.ui import _menu_status_devices, menu_status


def _keyboard_only_entries(entries: list[dict]) -> list[dict]:
    return [e for e in entries if e.get("device_type") == "keyboard"]


def _virtual_entries(entries: list[dict]) -> list[dict]:
    return [e for e in entries if e.get("device_type") in {"logo", "neon", "vent"}]


def _patch_effective_virtual_routes(monkeypatch: pytest.MonkeyPatch, *, available: bool) -> None:
    monkeypatch.setattr(
        _menu_status_devices,
        "iter_effective_secondary_routes",
        lambda: (
            tuple(
                EffectiveSecondaryRoute(
                    route=route,
                    available=available,
                    simulated=False,
                    availability_source="test",
                )
                for route in iter_virtual_routes()
            )
            if available
            else ()
        ),
    )


def test_device_context_entries_include_virtual_routes_when_parent_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_effective_virtual_routes(monkeypatch, available=True)

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
    _patch_effective_virtual_routes(monkeypatch, available=False)

    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
    )

    entries = menu_status.device_context_entries(tray)

    assert _virtual_entries(entries) == []
    assert len(_keyboard_only_entries(entries)) == 1


def test_virtual_route_text_uses_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_effective_virtual_routes(monkeypatch, available=True)

    tray = SimpleNamespace(
        backend=None,
        backend_probe=SimpleNamespace(identifiers={"usb_vid": "0x048d", "usb_pid": "0xc197"}),
        device_discovery={"candidates": []},
    )

    entries = menu_status.device_context_entries(tray)
    texts = {e["device_type"]: e["text"] for e in entries if e.get("device_type") in {"logo", "neon", "vent"}}

    assert texts == {
        "logo": "Logo (shared controller 048d:c197)",
        "neon": "Neon Strip (shared controller 048d:c197)",
        "vent": "Vents (shared controller 048d:c197)",
    }


def test_simulation_context_entries_expose_all_registered_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")

    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
    )

    entries = menu_status.device_context_entries(tray)

    assert [entry["device_type"] for entry in entries[1:]] == ["lightbar", "mouse", "logo", "neon", "vent"]
    assert all("(simulated)" in entry["text"] for entry in entries[1:])


def test_registered_route_is_not_duplicated_when_discovery_candidate_matches() -> None:
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
                    "probe_names": ["ite8233_none_chassis_lightbar_clevo"],
                }
            ]
        },
    )

    entries = menu_status.device_context_entries(tray)

    assert [entry.get("device_type") for entry in entries].count("lightbar") == 1
