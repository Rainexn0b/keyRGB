"""Hardware-free integration: composite secondary scene + config-apply plan + forced-off.

Covers the multi-layer seam that unit slices alone miss: profile-owned secondary
static apply must not run while any forced-off flag is set, and config-apply
classification still reports the correct pure plan/mode.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.core.secondary_device_routes import SecondaryDeviceRoute
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.tray.controllers.secondary_static_scene import apply_secondary_static_scene
from src.tray.idle_power_state import set_idle_power_state_field
from src.tray.pollers.config_polling_internal._apply_plan import classify_config_apply_plan
from src.tray.pollers.config_polling_internal.core import ConfigApplyState
from tests.tray.fakes import make_owner_backed_simple_tray


class _Device:
    def __init__(self, key: str, calls: list[tuple[str, str]]) -> None:
        self.key = key
        self.calls = calls

    def set_color(self, color: object, *, brightness: int) -> None:
        self.calls.append((self.key, "set_color"))

    def turn_off(self) -> None:
        self.calls.append((self.key, "turn_off"))

    def close(self) -> None:
        self.calls.append((self.key, "close"))


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


def _tray(*, power_forced_off: bool = False) -> SimpleNamespace:
    logo = _route("logo")
    neon = _route("neon")
    areas = {
        "logo": {"enabled": True, "color": [255, 0, 0]},
        "neon": {"enabled": True, "color": [0, 255, 0]},
    }
    return make_owner_backed_simple_tray(
        is_off=True,
        power_forced_off=power_forced_off,
        user_forced_off=False,
        idle_forced_off=False,
        config=SimpleNamespace(_settings={"secondary_device_state": areas}),
        _routes=(logo, neon),
    )


def test_forced_off_blocks_secondary_static_scene_while_plan_stays_pure() -> None:
    tray = _tray(power_forced_off=True)
    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=True
    )
    calls: list[tuple[str, str]] = []
    routes = tray._routes

    ok = apply_secondary_static_scene(
        tray,
        effective_routes_fn=lambda: tuple(_effective(r) for r in routes),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )
    assert ok is False
    assert calls == []

    plan = classify_config_apply_plan(
        configured_effect="perkey",
        current=ConfigApplyState(
            effect="perkey",
            selected_effect="perkey",
            speed=4,
            brightness=25,
            color=(1, 2, 3),
            perkey_sig=(((0, 0), (10, 20, 30)),),
            reactive_use_manual=False,
            reactive_color=(255, 255, 255),
            secondary_sig=(("logo", (("enabled", True), ("color", (255, 0, 0)))),),
        ),
    )
    assert plan.execution_kind == "apply"
    assert plan.apply_mode == "perkey"
    assert plan.persist_effect is None


def test_cleared_forced_off_applies_enabled_secondary_routes() -> None:
    tray = _tray(power_forced_off=False)
    calls: list[tuple[str, str]] = []
    routes = tray._routes

    ok = apply_secondary_static_scene(
        tray,
        payload={"version": 1, "areas": tray.config._settings["secondary_device_state"]},
        effective_routes_fn=lambda: tuple(_effective(r) for r in routes),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )
    assert ok is True
    assert ("logo", "set_color") in calls
    assert ("neon", "set_color") in calls


def test_clearing_forced_off_then_applies_secondary_and_keeps_plan_pure() -> None:
    """Multi-layer: forced-off gate → clear via helper → static apply + pure plan."""
    tray = _tray(power_forced_off=True)
    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=True
    )
    calls: list[tuple[str, str]] = []
    routes = tray._routes
    payload = {"version": 1, "areas": tray.config._settings["secondary_device_state"]}

    assert (
        apply_secondary_static_scene(
            tray,
            payload=payload,
            effective_routes_fn=lambda: tuple(_effective(r) for r in routes),
            acquire_device_fn=lambda route: _Device(route.state_key, calls),
        )
        is False
    )
    assert calls == []

    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=False
    )
    assert tray.tray_idle_power_state.power_forced_off is False

    ok = apply_secondary_static_scene(
        tray,
        payload=payload,
        effective_routes_fn=lambda: tuple(_effective(r) for r in routes),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )
    assert ok is True
    assert ("logo", "set_color") in calls
    assert ("neon", "set_color") in calls

    plan = classify_config_apply_plan(
        configured_effect="static",
        current=ConfigApplyState(
            effect="static",
            selected_effect="static",
            speed=3,
            brightness=20,
            color=(10, 20, 30),
            perkey_sig=(),
            reactive_use_manual=False,
            reactive_color=(255, 255, 255),
            secondary_sig=(("logo", (("enabled", True), ("color", (255, 0, 0)))),),
        ),
    )
    assert plan.execution_kind == "apply"
    assert plan.apply_mode in {"uniform", "effect", "perkey"}
