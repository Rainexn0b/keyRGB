from __future__ import annotations

from types import SimpleNamespace

from src.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.tray.controllers.secondary_static_scene import (
    apply_secondary_static_route,
    apply_secondary_static_scene,
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
    from src.core.secondary_device_routes import iter_secondary_routes

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
    from src.core import secondary_device_routes as routes_mod
    from src.tray.controllers import secondary_static_scene as scene

    old_routes = routes_mod.iter_secondary_routes()
    areas = {
        route.state_key: {"enabled": False, "color": [1, 2, 3]}
        for route in old_routes
        if route.supports_profile_state
    }
    assert scene.authoritative_payload_from_config(
        SimpleNamespace(_settings={"secondary_device_state": areas})
    ) is not None

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
    assert scene.authoritative_payload_from_config(
        SimpleNamespace(_settings={"secondary_device_state": areas})
    ) is None


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


def test_static_scene_applies_enabled_and_disabled_profile_areas_and_closes_devices() -> None:
    calls: list[tuple[str, str, object]] = []
    mouse = _route("mouse")
    logo = _route("logo")
    devices = {key: _Device(key, calls) for key in ("mouse", "logo")}
    tray = SimpleNamespace(
        config=SimpleNamespace(get_secondary_device_brightness=lambda *_args, **_kwargs: 33),
        _active_secondary_lighting={
            "version": 1,
            "areas": {
                "mouse": {"enabled": True, "color": [1, 2, 3]},
                "logo": {"enabled": False, "color": [4, 5, 6]},
            },
        },
    )

    assert (
        apply_secondary_static_scene(
            tray,
            effective_routes_fn=lambda: (_effective(mouse), _effective(logo)),
            acquire_device_fn=lambda route: devices[route.state_key],
        )
        is True
    )

    assert ("mouse", "set_color", ((1, 2, 3), 33)) in calls
    assert ("logo", "turn_off", None) in calls
    assert calls.count(("mouse", "close", None)) == 1
    assert calls.count(("logo", "close", None)) == 1


def test_explicit_empty_static_scene_turns_off_all_available_profile_routes() -> None:
    calls: list[tuple[str, str, object]] = []
    mouse = _route("mouse")
    logo = _route("logo")
    tray = SimpleNamespace(config=SimpleNamespace(), _active_secondary_lighting={"version": 1, "areas": {}})

    assert (
        apply_secondary_static_scene(
            tray,
            effective_routes_fn=lambda: (_effective(mouse), _effective(logo)),
            acquire_device_fn=lambda route: _Device(route.state_key, calls),
        )
        is True
    )

    assert ("mouse", "turn_off", None) in calls
    assert ("logo", "turn_off", None) in calls


def test_partial_static_scene_turns_off_omitted_available_profile_route() -> None:
    calls: list[tuple[str, str, object]] = []
    mouse = _route("mouse")
    logo = _route("logo")
    tray = SimpleNamespace(
        config=SimpleNamespace(),
        _active_secondary_lighting={"areas": {"mouse": {"enabled": True, "color": [7, 8, 9]}}},
    )

    apply_secondary_static_scene(
        tray,
        effective_routes_fn=lambda: (_effective(mouse), _effective(logo)),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )

    assert ("mouse", "set_color", ((7, 8, 9), 25)) in calls
    assert ("logo", "turn_off", None) in calls


def test_issue7_legacy_profile_static_scene_falls_back_to_saved_config_state() -> None:
    calls: list[tuple[str, str, object]] = []
    colors = {
        "logo": (255, 0, 0),
        "neon": (0, 255, 0),
        "vent": (0, 0, 255),
    }
    routes = tuple(
        SecondaryDeviceRoute(
            device_type=key,
            backend_name=f"ite8258-chassis-{key}",
            display_name=key.title(),
            state_key=f"ite8258_chassis_{key}",
            get_backend=lambda: object(),
            get_device=lambda: object(),
            config_brightness_attr=f"ite8258_chassis_{key}_brightness",
            config_color_attr=f"ite8258_chassis_{key}_color",
            supports_uniform_color=True,
            supports_profile_state=True,
            brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        )
        for key in colors
    )
    tray = SimpleNamespace(
        config=SimpleNamespace(
            brightness=40,
            get_secondary_device_enabled=lambda *_args, **_kwargs: True,
            get_secondary_device_color=lambda state_key, **_kwargs: colors[state_key.rsplit("_", 1)[-1]],
        )
        # Deliberately no _active_secondary_lighting: this is an upgraded
        # Issue #7 installation whose legacy profile has no component file.
    )

    assert (
        apply_secondary_static_scene(
            tray,
            effective_routes_fn=lambda: tuple(_effective(route) for route in routes),
            acquire_device_fn=lambda route: _Device(route.device_type, calls),
        )
        is True
    )

    assert {(key, action, payload) for key, action, payload in calls if action == "set_color"} == {
        ("logo", "set_color", ((255, 0, 0), 40)),
        ("neon", "set_color", ((0, 255, 0), 40)),
        ("vent", "set_color", ((0, 0, 255), 40)),
    }


def test_static_scene_isolates_one_route_failure() -> None:
    calls: list[tuple[str, str, object]] = []
    failed = _route("failed")
    healthy = _route("healthy")

    def acquire(route: SecondaryDeviceRoute) -> object:
        if route.state_key == "failed":
            raise OSError("route unavailable")
        return _Device(route.state_key, calls)

    tray = SimpleNamespace(
        config=SimpleNamespace(),
        _active_secondary_lighting={"areas": {"failed": {}, "healthy": {"color": [7, 8, 9]}}},
    )

    assert (
        apply_secondary_static_scene(
            tray,
            effective_routes_fn=lambda: (_effective(failed), _effective(healthy)),
            acquire_device_fn=acquire,
        )
        is True
    )
    assert ("healthy", "set_color", ((7, 8, 9), 25)) in calls


def test_static_scene_uses_legacy_brightness_as_enabled_fallback() -> None:
    calls: list[tuple[str, str, object]] = []
    route = _route("logo")
    tray = SimpleNamespace(
        config=SimpleNamespace(),
        _active_secondary_lighting={"areas": {"logo": {"brightness": 0, "color": [7, 8, 9]}}},
    )

    apply_secondary_static_scene(
        tray,
        effective_routes_fn=lambda: (_effective(route),),
        acquire_device_fn=lambda _route: _Device("logo", calls),
    )

    assert ("logo", "turn_off", None) in calls
    assert not any(action == "set_color" for _key, action, _payload in calls)


def test_static_scene_does_not_write_while_forced_off() -> None:
    from tests.tray.fakes import make_owner_backed_simple_tray

    calls: list[SecondaryDeviceRoute] = []
    route = _route("mouse")
    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        user_forced_off=True,
        _active_secondary_lighting={"areas": {"mouse": {"enabled": True}}},
    )

    assert (
        apply_secondary_static_scene(
            tray,
            effective_routes_fn=lambda: (_effective(route),),
            acquire_device_fn=lambda selected: calls.append(selected) or _Device("mouse", []),
        )
        is False
    )
    assert calls == []


def test_shared_brightness_route_uses_primary_keyboard_brightness() -> None:
    calls: list[tuple[str, str, object]] = []
    route = _route("logo")
    route = SecondaryDeviceRoute(
        **{
            **route.__dict__,
            "brightness_policy": BRIGHTNESS_POLICY_PRIMARY_SHARED,
        }
    )
    tray = SimpleNamespace(
        config=SimpleNamespace(
            brightness=40,
            get_secondary_device_brightness=lambda *_args, **_kwargs: 10,
        ),
        _active_secondary_lighting={"areas": {"logo": {"enabled": True, "color": [1, 2, 3]}}},
    )

    apply_secondary_static_scene(
        tray,
        effective_routes_fn=lambda: (_effective(route),),
        acquire_device_fn=lambda _route: _Device("logo", calls),
    )

    assert ("logo", "set_color", ((1, 2, 3), 40)) in calls


def test_independent_route_uses_active_profile_brightness() -> None:
    calls: list[tuple[str, str, object]] = []
    base = _route("lightbar")
    route = SecondaryDeviceRoute(
        **{
            **base.__dict__,
            "brightness_policy": BRIGHTNESS_POLICY_INDEPENDENT,
        }
    )
    tray = SimpleNamespace(
        config=SimpleNamespace(get_secondary_device_brightness=lambda *_args, **_kwargs: 10),
        _active_secondary_lighting={"areas": {"lightbar": {"enabled": True, "color": [1, 2, 3], "brightness": 35}}},
    )

    apply_secondary_static_scene(
        tray,
        effective_routes_fn=lambda: (_effective(route),),
        acquire_device_fn=lambda _route: _Device("lightbar", calls),
    )

    assert ("lightbar", "set_color", ((1, 2, 3), 35)) in calls


def test_apply_one_shared_route_uses_profile_color_and_primary_brightness() -> None:
    calls: list[tuple[str, str, object]] = []
    base = _route("logo")
    route = SecondaryDeviceRoute(
        **{
            **base.__dict__,
            "brightness_policy": BRIGHTNESS_POLICY_PRIMARY_SHARED,
        }
    )
    tray = SimpleNamespace(
        config=SimpleNamespace(brightness=45),
        _active_secondary_lighting={"areas": {"logo": {"enabled": True, "color": [4, 5, 6]}}},
    )

    assert (
        apply_secondary_static_route(
            tray,
            route,
            acquire_device_fn=lambda _route: _Device("logo", calls),
        )
        is True
    )

    assert ("logo", "set_color", ((4, 5, 6), 45)) in calls
    assert ("logo", "close", None) in calls


def test_global_profile_area_turn_off_is_independent_of_effect_target() -> None:
    calls: list[tuple[str, str, object]] = []
    route = _route("mouse")
    tray = SimpleNamespace(config=SimpleNamespace(), _active_secondary_lighting={"areas": {"mouse": {}}})

    turn_off_secondary_profile_areas(
        tray,
        effective_routes_fn=lambda: (_effective(route),),
        acquire_device_fn=lambda _route: _Device("mouse", calls),
    )

    assert ("mouse", "turn_off", None) in calls
    assert ("mouse", "close", None) in calls


def test_global_profile_area_turn_off_covers_legacy_scene_without_payload() -> None:
    calls: list[tuple[str, str, object]] = []
    mouse = _route("mouse")
    tray = SimpleNamespace(config=SimpleNamespace())

    turn_off_secondary_profile_areas(
        tray,
        effective_routes_fn=lambda: (_effective(mouse),),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )

    assert ("mouse", "turn_off", None) in calls
    assert ("mouse", "close", None) in calls


def test_animated_secondary_targets_follow_active_profile_enabled_routes(monkeypatch) -> None:
    from src.core.secondary_device_runtime import SIMULATION_ENVIRONMENT_VARIABLE
    from src.tray.controllers.software_target_controller import secondary_software_render_targets

    monkeypatch.setenv(SIMULATION_ENVIRONMENT_VARIABLE, "1")
    tray = SimpleNamespace(
        config=SimpleNamespace(software_effect_target="all_uniform_capable"),
        engine=SimpleNamespace(),
        software_target_proxy_cache={},
        _active_secondary_lighting={
            "areas": {
                "mouse": {"enabled": True},
                "ite8258_chassis_logo": {"enabled": False},
            }
        },
    )

    targets = secondary_software_render_targets(tray)

    assert [target._route.state_key for target in targets] == ["mouse"]
