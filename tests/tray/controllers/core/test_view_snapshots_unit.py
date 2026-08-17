from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.power.system import PowerMode, PowerModeStatus
from src.tray.controllers import view_snapshots


def test_refresh_system_power_snapshot_stores_observed_status() -> None:
    tray = SimpleNamespace()
    status = PowerModeStatus(
        supported=True,
        mode=PowerMode.BALANCED,
        reason="ok",
        identifiers={"can_apply": "true"},
    )

    stored = view_snapshots.refresh_system_power_snapshot(tray, get_status=lambda: status)

    assert stored is status
    assert tray.system_power_status is status
    assert view_snapshots.read_system_power_status(tray) is status


def test_refresh_system_power_snapshot_swallows_recoverable_observer_errors() -> None:
    tray = SimpleNamespace(system_power_status="stale")

    stored = view_snapshots.refresh_system_power_snapshot(
        tray,
        get_status=lambda: (_ for _ in ()).throw(OSError("cpufreq missing")),
    )

    assert stored is None
    assert tray.system_power_status is None
    assert view_snapshots.read_system_power_status(tray) is None


def test_refresh_system_power_snapshot_propagates_unexpected_errors() -> None:
    tray = SimpleNamespace()

    with pytest.raises(AssertionError, match="observer bug"):
        view_snapshots.refresh_system_power_snapshot(
            tray,
            get_status=lambda: (_ for _ in ()).throw(AssertionError("observer bug")),
        )


def test_read_system_power_status_is_presentation_only() -> None:
    tray = SimpleNamespace()
    calls: list[str] = []

    view_snapshots.refresh_system_power_snapshot(
        tray,
        get_status=lambda: calls.append("observe") or SimpleNamespace(supported=True, mode="balanced"),
    )
    assert calls == ["observe"]

    assert view_snapshots.read_system_power_status(tray) is tray.system_power_status
    assert calls == ["observe"]


def test_refresh_effective_secondary_routes_snapshot_stores_tuple() -> None:
    tray = SimpleNamespace()
    routes = (SimpleNamespace(available=True, route=SimpleNamespace(supports_profile_state=True)),)

    stored = view_snapshots.refresh_effective_secondary_routes_snapshot(tray, collect=lambda: routes)

    assert stored == routes
    assert tray.effective_secondary_routes == routes
    assert view_snapshots.read_effective_secondary_routes(tray) == routes
    assert view_snapshots.secondary_profile_routes_available(tray) is True


def test_missing_secondary_snapshot_does_not_probe() -> None:
    tray = SimpleNamespace()

    assert view_snapshots.read_effective_secondary_routes(tray) == ()
    assert view_snapshots.secondary_profile_routes_available(tray) is False
