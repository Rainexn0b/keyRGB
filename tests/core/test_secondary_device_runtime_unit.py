"""Unit contracts for the central secondary-device runtime and simulation."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.core.secondary_device_routes import (
    SecondaryDeviceRoute,
    iter_secondary_routes,
    route_for_device_type,
)
from src.core.secondary_device_runtime import (
    SIMULATION_ENVIRONMENT_VARIABLE,
    acquire_secondary_device,
    backend_for_secondary_route,
    has_available_secondary_profile_routes,
    iter_effective_secondary_routes,
    reset_simulated_secondary_devices,
    route_is_available,
    secondary_device_simulation_enabled,
)


@pytest.fixture(autouse=True)
def _reset_simulation_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(SIMULATION_ENVIRONMENT_VARIABLE, raising=False)
    reset_simulated_secondary_devices()
    yield
    reset_simulated_secondary_devices()


def _route(
    device_type: str, *, parent: str | None = None, state_key: str | None = None, backend=None
) -> SecondaryDeviceRoute:
    return SecondaryDeviceRoute(
        device_type=device_type,
        backend_name=f"test-{device_type}",
        display_name=device_type.title(),
        state_key=state_key or f"test_{device_type}",
        get_backend=backend or (lambda: SimpleNamespace(is_available=lambda: True)),
        get_device=lambda: object(),
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
        parent_backend_name=parent,
        zone_key=device_type if parent else None,
    )


def test_simulation_flag_normalizes_common_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, value)
        assert secondary_device_simulation_enabled() is True

    for value in ("", "0", "false", "no", "off", "unexpected"):
        monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, value)
        assert secondary_device_simulation_enabled() is False


def test_simulation_exposes_all_five_registered_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")

    effective = iter_effective_secondary_routes()

    assert [entry.state_key for entry in effective] == [
        "lightbar",
        "mouse",
        "ite8258_chassis_logo",
        "ite8258_chassis_neon",
        "ite8258_chassis_vent",
    ]
    assert len({entry.state_key for entry in effective}) == 5
    assert all(entry.available for entry in effective)
    assert all(entry.simulated for entry in effective)
    assert {entry.availability_source for entry in effective} == {"simulation"}


def test_simulation_deduplicates_matching_state_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    first = _route("logo", state_key="same")
    duplicate = replace(first, backend_name="test-logo-duplicate", display_name="Duplicate Logo")

    effective = iter_effective_secondary_routes([first, duplicate, _route("neon")])

    assert [entry.state_key for entry in effective] == ["same", "test_neon"]
    assert effective[0].display_name == "Logo"


def test_simulation_never_calls_real_probe_or_device_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")

    def explode_probe():
        raise AssertionError("real secondary backend probe was called")

    def explode_device():
        raise AssertionError("real secondary get_device was called")

    route = replace(
        _route("tripwire"),
        get_backend=explode_probe,
        get_device=explode_device,
    )

    assert iter_effective_secondary_routes([route])[0].simulated is True
    assert route_is_available(route) is True
    device = acquire_secondary_device(route)
    assert device.device_type == "tripwire"
    assert backend_for_secondary_route(route).is_available() is True


def test_simulated_device_supports_uniform_state_readback_and_idempotent_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    route = route_for_device_type("logo")
    assert route is not None

    device = acquire_secondary_device(route)
    device.set_color((300, -5, 17), brightness=150)

    assert device.get_color() == (255, 0, 17)
    assert device.get_brightness() == 100
    assert device.is_off() is False

    device.set_brightness(0)
    assert device.is_off() is True
    device.set_color((1, 2, 3), brightness=20)
    assert device.is_off() is False

    device.close()
    device.close()
    with pytest.raises(RuntimeError, match="closed"):
        device.get_brightness()

    # A new acquisition sees the same in-memory route state, while getting a
    # fresh open handle after the prior handle was closed.
    reopened = acquire_secondary_device(route)
    assert reopened.get_color() == (1, 2, 3)
    assert reopened.get_brightness() == 20


def test_simulated_device_rejects_per_key_and_hardware_effect_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    route = route_for_device_type("vent")
    assert route is not None
    device = acquire_secondary_device(route)

    with pytest.raises(NotImplementedError, match="uniform colour only"):
        device.set_key_colors({(0, 0): (255, 0, 0)}, brightness=50)
    with pytest.raises(NotImplementedError, match="hardware effects"):
        device.set_effect({"effect": "rainbow"})


def test_real_snapshot_probes_shared_parent_once_and_preserves_order() -> None:
    calls = 0

    class _Backend:
        def is_available(self) -> bool:
            nonlocal calls
            calls += 1
            return True

    backend = _Backend()
    routes = [
        _route("logo", parent="shared-parent", backend=lambda: backend),
        _route("neon", parent="shared-parent", backend=lambda: backend),
        _route("vent", parent="shared-parent", backend=lambda: backend),
        _route("standalone", backend=lambda: backend),
    ]

    effective = iter_effective_secondary_routes(routes)

    assert [entry.device_type for entry in effective] == ["logo", "neon", "vent", "standalone"]
    assert calls == 2  # one shared parent probe + one standalone backend probe
    assert all(entry.availability_source == "parent_probe" for entry in effective[:3])
    assert effective[3].availability_source == "backend_probe"


def test_real_snapshot_deduplicates_matching_state_keys() -> None:
    routes = [_route("first", state_key="same"), _route("second", state_key="same"), _route("third")]

    effective = iter_effective_secondary_routes(routes)

    assert [entry.state_key for entry in effective] == ["same", "test_third"]


def test_unavailable_real_routes_are_omitted_unless_requested() -> None:
    unavailable = _route("missing", backend=lambda: SimpleNamespace(is_available=lambda: False))

    assert iter_effective_secondary_routes([unavailable]) == ()
    included = iter_effective_secondary_routes([unavailable], include_unavailable=True)
    assert len(included) == 1
    assert included[0].available is False
    assert included[0].availability_source == "backend_probe"


def test_profile_route_availability_requires_profile_compatible_route() -> None:
    profile_route = _route("profile")
    effect_only_route = replace(_route("effect-only"), supports_profile_state=False)

    assert has_available_secondary_profile_routes([profile_route]) is True
    assert has_available_secondary_profile_routes([effect_only_route]) is False


def test_runtime_uses_registered_route_catalog_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")

    assert {entry.route for entry in iter_effective_secondary_routes()} == set(iter_secondary_routes())
