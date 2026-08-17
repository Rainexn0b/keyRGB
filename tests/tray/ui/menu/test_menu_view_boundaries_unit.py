from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.power.system import PowerMode
from src.tray.ui import menu as tray_menu, menu_sections, menu_status
from tests.tray.ui.menu.test_tray_menu_capabilities_unit import (
    DummyCaps,
    DummyTray,
    FakePystray,
    fake_item,
)


def test_menu_construction_does_not_query_os_power_or_probe_secondary_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_status() -> object:
        raise AssertionError("menu must not observe cpufreq")

    def _fail_routes() -> object:
        raise AssertionError("menu must not probe secondary routes")

    monkeypatch.setattr("src.core.power.system.get_status", _fail_status)
    monkeypatch.setattr("src.core.power.system._observe.get_status", _fail_status)
    monkeypatch.setattr("src.core.secondary_device_runtime.iter_effective_secondary_routes", _fail_routes)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.system_power_status = SimpleNamespace(
        supported=True,
        identifiers={"can_apply": "true"},
        mode=PowerMode.BALANCED,
    )
    tray.engine._ensure_device_available = lambda: (_ for _ in ()).throw(
        AssertionError("menu must not acquire hardware")
    )

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    labels = [item["text"] for item in items if isinstance(item, dict)]
    assert "Power Mode" in labels


def test_system_power_checked_callbacks_use_captured_snapshot_mode() -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.system_power_status = SimpleNamespace(
        supported=True,
        identifiers={"can_apply": "true"},
        mode=PowerMode.PERFORMANCE,
    )

    power_menu = menu_sections.build_system_power_mode_menu(tray, pystray=FakePystray, item=fake_item)
    assert power_menu is not None

    checked = {
        entry["text"]: entry["checked"](None)
        for entry in power_menu.items
        if isinstance(entry, dict) and callable(entry.get("checked"))
    }
    assert checked == {
        "Extreme Saver": False,
        "Balanced": False,
        "Performance": True,
    }


def test_device_context_entries_do_not_call_live_effective_route_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.core.secondary_device_runtime.iter_effective_secondary_routes",
        lambda: (_ for _ in ()).throw(AssertionError("live probe")),
    )

    tray = SimpleNamespace(
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
        engine=SimpleNamespace(device_available=True),
    )

    entries = menu_status.device_context_entries(tray)

    assert [entry.get("device_type") for entry in entries] == ["keyboard"]
