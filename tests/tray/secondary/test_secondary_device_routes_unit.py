from __future__ import annotations

import pytest

from keyrgb.core.secondary_device_routes import (
    BRIGHTNESS_POLICIES,
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    BRIGHTNESS_POLICY_UNSUPPORTED,
    iter_parent_backend_names,
    iter_secondary_routes,
    iter_virtual_routes,
    route_for_backend_name,
    route_for_context_entry,
    route_for_device_type,
)

_VIRTUAL_DEVICE_TYPES = {"logo", "neon", "vent"}


def test_all_virtual_routes_belong_to_ite8258_chassis_parent() -> None:
    virtual = iter_virtual_routes()

    assert len(virtual) == 3
    for route in virtual:
        assert route.parent_backend_name == "ite8258_perkey_chassis"
        assert route.zone_key in _VIRTUAL_DEVICE_TYPES
        assert route.device_type in _VIRTUAL_DEVICE_TYPES
        assert route.supports_uniform_color is True
        assert route.supports_software_target is True


def test_iter_parent_backend_names_returns_ite8258_chassis() -> None:
    assert iter_parent_backend_names() == {"ite8258_perkey_chassis"}


def test_virtual_routes_have_distinct_backend_names_and_state_keys() -> None:
    virtual = iter_virtual_routes()

    backend_names = {route.backend_name for route in virtual}
    state_keys = {route.state_key for route in virtual}
    device_types = {route.device_type for route in virtual}

    assert backend_names == {"ite8258-chassis-logo", "ite8258-chassis-neon", "ite8258-chassis-vent"}
    assert state_keys == {"ite8258_chassis_logo", "ite8258_chassis_neon", "ite8258_chassis_vent"}
    assert device_types == _VIRTUAL_DEVICE_TYPES


def test_route_for_backend_name_finds_virtual_routes() -> None:
    for zone in _VIRTUAL_DEVICE_TYPES:
        route = route_for_backend_name(f"ite8258-chassis-{zone}")
        assert route is not None
        assert route.device_type == zone
        assert route.backend_name == f"ite8258-chassis-{zone}"


def test_route_for_device_type_finds_virtual_routes() -> None:
    for zone in _VIRTUAL_DEVICE_TYPES:
        route = route_for_device_type(zone)
        assert route is not None
        assert route.device_type == zone


def test_route_for_context_entry_prefers_backend_name_match() -> None:
    entry = {"backend_name": "ite8258-chassis-logo", "device_type": "mouse"}

    route = route_for_context_entry(entry)

    assert route is not None
    assert route.backend_name == "ite8258-chassis-logo"


def test_route_for_context_entry_falls_back_to_device_type() -> None:
    entry = {"device_type": "neon"}

    route = route_for_context_entry(entry)

    assert route is not None
    assert route.device_type == "neon"


def test_virtual_routes_carry_config_attr_names() -> None:
    route = route_for_backend_name("ite8258-chassis-logo")
    assert route is not None
    assert route.config_brightness_attr == "ite8258_chassis_logo_brightness"
    assert route.config_color_attr == "ite8258_chassis_logo_color"


def test_legacy_routes_have_no_parent_backend_or_zone_key() -> None:
    lightbar = route_for_backend_name("ite8233_none_chassis_lightbar_clevo")
    mouse = route_for_backend_name("sysfs-mouse")

    assert lightbar is not None
    assert mouse is not None
    assert lightbar.parent_backend_name is None
    assert lightbar.zone_key is None
    assert mouse.parent_backend_name is None
    assert mouse.zone_key is None


def test_secondary_device_route_is_frozen() -> None:
    route = route_for_backend_name("ite8233_none_chassis_lightbar_clevo")
    assert route is not None

    with pytest.raises(AttributeError):
        route.display_name = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Phase 1: all-route enumeration + extended metadata (supports_profile_state,
# brightness_policy). These underpin the central runtime provider, simulation,
# diagnostics, and the Lighting areas editor, which must not silently drop the
# standalone Lightbar / Mouse routes.
# ---------------------------------------------------------------------------


def test_iter_secondary_routes_returns_every_registered_route() -> None:
    routes = iter_secondary_routes()

    # The full catalogue is Clevo lightbar + Tongfang front lightbar + Mouse
    # + the three composite zones. Both lightbars share device_type="lightbar"
    # but have distinct backend_name/state_key identities.
    assert {route.device_type for route in routes} == {"lightbar", "mouse", "logo", "neon", "vent"}
    # Ordering is stable and deterministic (see test_iter_secondary_routes_ordering_is_stable).
    assert [route.device_type for route in routes] == [
        "lightbar",
        "lightbar",
        "mouse",
        "logo",
        "neon",
        "vent",
    ]
    assert [route.backend_name for route in routes] == [
        "ite8233_none_chassis_lightbar_clevo",
        "ite8291_none_chassis_lightbar_tongfang",
        "sysfs-mouse",
        "ite8258-chassis-logo",
        "ite8258-chassis-neon",
        "ite8258-chassis-vent",
    ]


def test_iter_secondary_routes_is_a_superset_of_virtual_routes() -> None:
    virtual = iter_virtual_routes()
    all_routes = iter_secondary_routes()

    virtual_keys = {route.state_key for route in virtual}
    all_keys = {route.state_key for route in all_routes}

    assert virtual_keys.issubset(all_keys)
    # iter_secondary_routes additionally includes the standalone routes.
    assert all_keys - virtual_keys == {"lightbar", "ite8291_tongfang_lightbar", "mouse"}


def test_iter_secondary_routes_ordering_is_stable() -> None:
    # Deterministic ordering is required so effective-route snapshots and
    # diagnostics output are reproducible.
    first = [route.state_key for route in iter_secondary_routes()]
    second = [route.state_key for route in iter_secondary_routes()]
    assert first == second
    assert len(first) == len(set(first))  # no duplicates, by state_key


def test_every_route_carries_profile_and_brightness_metadata() -> None:
    for route in iter_secondary_routes():
        assert isinstance(route.supports_profile_state, bool)
        assert route.brightness_policy in BRIGHTNESS_POLICIES, route


def test_all_uniform_capable_routes_are_profile_compatible() -> None:
    # Per the plan, every uniform-capable secondary route is a profile area.
    for route in iter_secondary_routes():
        if route.supports_uniform_color:
            assert route.supports_profile_state is True, route.device_type


def test_brightness_policy_matches_route_topology() -> None:
    lightbar = route_for_device_type("lightbar")
    mouse = route_for_device_type("mouse")
    assert lightbar is not None and mouse is not None

    # Standalone controllers own their own brightness.
    assert lightbar.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT
    assert mouse.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT
    assert lightbar.parent_backend_name is None
    assert mouse.parent_backend_name is None

    # Composite-controller zones share the primary brightness.
    for zone in _VIRTUAL_DEVICE_TYPES:
        route = route_for_device_type(zone)
        assert route is not None
        assert route.brightness_policy == BRIGHTNESS_POLICY_PRIMARY_SHARED, zone
        assert route.parent_backend_name == "ite8258_perkey_chassis"


def test_brightness_policy_constants_are_distinct_and_covered() -> None:
    assert BRIGHTNESS_POLICY_INDEPENDENT != BRIGHTNESS_POLICY_PRIMARY_SHARED
    assert BRIGHTNESS_POLICY_UNSUPPORTED not in {
        BRIGHTNESS_POLICY_INDEPENDENT,
        BRIGHTNESS_POLICY_PRIMARY_SHARED,
    }
    # Every declared policy is represented by at least one route, and
    # ``unsupported`` is the safe default (no route currently uses it, but the
    # constant must remain valid metadata).
    used = {route.brightness_policy for route in iter_secondary_routes()}
    assert {BRIGHTNESS_POLICY_INDEPENDENT, BRIGHTNESS_POLICY_PRIMARY_SHARED}.issubset(used)
    assert BRIGHTNESS_POLICY_UNSUPPORTED in BRIGHTNESS_POLICIES


# ---------------------------------------------------------------------------
# Tongfang/Ionico front lightbar (048d:6005): a second standalone route that
# shares device_type="lightbar" with the legacy Clevo ite8233 route.
# ---------------------------------------------------------------------------


def test_tongfang_front_lightbar_route_metadata() -> None:
    route = route_for_backend_name("ite8291_none_chassis_lightbar_tongfang")

    assert route is not None
    assert route.device_type == "lightbar"
    assert route.backend_name == "ite8291_none_chassis_lightbar_tongfang"
    assert route.display_name == "Front Lightbar"
    assert route.state_key == "ite8291_tongfang_lightbar"
    assert route.config_brightness_attr == "ite8291_tongfang_lightbar_brightness"
    assert route.config_color_attr == "ite8291_tongfang_lightbar_color"
    assert route.brightness_ui_max == 100
    assert route.supports_uniform_color is True
    assert route.supports_software_target is True
    assert route.supports_profile_state is True
    assert route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT
    assert route.parent_backend_name is None
    assert route.zone_key is None


def test_lightbar_routes_have_unique_state_keys_and_stable_order() -> None:
    routes = iter_secondary_routes()
    lightbars = [route for route in routes if route.device_type == "lightbar"]

    assert [route.backend_name for route in lightbars] == [
        "ite8233_none_chassis_lightbar_clevo",
        "ite8291_none_chassis_lightbar_tongfang",
    ]
    assert [route.state_key for route in lightbars] == [
        "lightbar",
        "ite8291_tongfang_lightbar",
    ]
    # Clevo route keeps the legacy index; the new route follows immediately.
    state_keys = [route.state_key for route in routes]
    assert state_keys.index("lightbar") < state_keys.index("ite8291_tongfang_lightbar")
    assert len(set(state_keys)) == len(state_keys)


def test_route_for_device_type_lightbar_keeps_legacy_fallback() -> None:
    route = route_for_device_type("lightbar")

    assert route is not None
    assert route.backend_name == "ite8233_none_chassis_lightbar_clevo"
    assert route.state_key == "lightbar"


def test_route_for_context_entry_resolves_tongfang_lightbar_by_backend_name() -> None:
    entry = {
        "backend_name": "ite8291_none_chassis_lightbar_tongfang",
        "device_type": "lightbar",
    }

    route = route_for_context_entry(entry)

    assert route is not None
    assert route.backend_name == "ite8291_none_chassis_lightbar_tongfang"
    assert route.state_key == "ite8291_tongfang_lightbar"
