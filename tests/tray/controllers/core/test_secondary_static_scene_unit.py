from __future__ import annotations

from types import SimpleNamespace

from keyrgb.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    SecondaryDeviceRoute,
)
from keyrgb.core.secondary_device_runtime import EffectiveSecondaryRoute
from keyrgb.tray.controllers.secondary_static_scene import (
    authoritative_payload_from_config,
    turn_off_secondary_profile_areas,
)


class _Device:
    def __init__(self, key: str, calls: list[tuple[str, str, object]]) -> None:
        self.key = key
        self.calls = calls

    def set_color(self, color: object, *, brightness: int) -> None:
        self.calls.append((self.key, "set_color", (color, brightness)))

    def turn_off(self) -> None:
        self.calls.append((self.key, "turn_off", None))

    def close(self) -> None:
        self.calls.append((self.key, "close", None))


def _route(key: str) -> SecondaryDeviceRoute:
    return SecondaryDeviceRoute(
        device_type=key,
        backend_name=f"backend-{key}",
        display_name=key.title(),
        state_key=key,
        get_backend=lambda: object(),
        get_device=lambda: object(),
        config_brightness_attr=f"{key}_brightness",
        supports_uniform_color=True,
        supports_software_target=True,
        supports_profile_state=True,
    )


def _effective(route: SecondaryDeviceRoute) -> EffectiveSecondaryRoute:
    return EffectiveSecondaryRoute(
        route=route,
        available=True,
        simulated=True,
        availability_source="simulation",
    )


def test_default_empty_secondary_config_mirror_is_not_an_explicit_off_scene() -> None:
    config = SimpleNamespace(_settings={"secondary_device_state": {}})

    assert authoritative_payload_from_config(config) is None


def test_authoritative_payload_uses_readonly_secondary_snapshot_api() -> None:
    config = SimpleNamespace(
        secondary_device_state_snapshot=lambda: {
            "logo": {"enabled": True},
        }
    )

    assert authoritative_payload_from_config(config) is None


def test_partial_legacy_secondary_config_mirror_is_not_an_explicit_off_scene() -> None:
    config = SimpleNamespace(
        _settings={
            "secondary_device_state": {
                "ite8258_chassis_logo": {"brightness": 25, "color": [1, 2, 3]},
            }
        }
    )

    assert authoritative_payload_from_config(config) is None


def test_complete_profile_mirror_builds_authoritative_payload() -> None:
    from keyrgb.core.secondary_device_routes import iter_secondary_routes

    areas = {
        route.state_key: {
            "enabled": route.state_key == "ite8258_chassis_logo",
            "color": [1, 2, 3],
        }
        for route in iter_secondary_routes()
        if route.supports_profile_state
    }
    config = SimpleNamespace(_settings={"secondary_device_state": areas})

    assert authoritative_payload_from_config(config) == {"version": 1, "areas": areas}


def test_unknown_route_entries_do_not_satisfy_known_route_completeness() -> None:
    config = SimpleNamespace(
        _settings={
            "secondary_device_state": {
                "future_route": {"enabled": True, "color": [9, 9, 9]},
            }
        }
    )

    assert authoritative_payload_from_config(config) is None


def test_simulated_new_registered_route_makes_old_mirror_non_authoritative(monkeypatch) -> None:
    from keyrgb.core import secondary_device_routes as routes_mod
    from keyrgb.tray.controllers import secondary_static_scene as scene

    old_routes = routes_mod.iter_secondary_routes()
    areas = {
        route.state_key: {"enabled": False, "color": [1, 2, 3]} for route in old_routes if route.supports_profile_state
    }
    assert (
        scene.authoritative_payload_from_config(SimpleNamespace(_settings={"secondary_device_state": areas}))
        is not None
    )

    extra = SecondaryDeviceRoute(
        device_type="future",
        backend_name="future-backend",
        display_name="Future",
        state_key="future_area",
        get_backend=lambda: object(),
        get_device=lambda: object(),
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
    )
    monkeypatch.setattr(routes_mod, "_ROUTES", old_routes + (extra,))
    assert scene.authoritative_payload_from_config(SimpleNamespace(_settings={"secondary_device_state": areas})) is None


def test_global_off_skips_primary_owned_composite_routes() -> None:
    calls: list[tuple[str, str, object]] = []
    mouse = _route("mouse")
    logo = SecondaryDeviceRoute(
        **{
            **_route("logo").__dict__,
            "primary_owns_global_off": True,
        }
    )
    tray = SimpleNamespace(config=SimpleNamespace())

    turn_off_secondary_profile_areas(
        tray,
        effective_routes_fn=lambda: (_effective(mouse), _effective(logo)),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )

    assert ("mouse", "turn_off", None) in calls
    assert ("logo", "turn_off", None) not in calls
