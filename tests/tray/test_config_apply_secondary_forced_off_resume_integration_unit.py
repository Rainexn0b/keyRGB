"""Multi-layer: uniform/effect config plan + secondary static + forced-off skip/resume."""

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
    def __init__(self, key: str, calls: list[tuple[str, str, object]]) -> None:
        self.key = key
        self.calls = calls

    def set_color(self, color: object, *, brightness: int) -> None:
        self.calls.append((self.key, "set_color", color))

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


def test_forced_off_skips_secondary_then_resume_applies_uniform_plan() -> None:
    logo = _route("logo")
    neon = _route("neon")
    areas = {
        "logo": {"enabled": True, "color": [255, 10, 10]},
        "neon": {"enabled": True, "color": [10, 255, 10]},
    }
    tray = make_owner_backed_simple_tray(
        is_off=True,
        power_forced_off=True,
        user_forced_off=False,
        idle_forced_off=False,
        config=SimpleNamespace(_settings={"secondary_device_state": areas}),
        _routes=(logo, neon),
    )
    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=True
    )
    calls: list[tuple[str, str, object]] = []
    payload = {"version": 1, "areas": areas}

    assert (
        apply_secondary_static_scene(
            tray,
            payload=payload,
            effective_routes_fn=lambda: tuple(_effective(r) for r in tray._routes),
            acquire_device_fn=lambda route: _Device(route.state_key, calls),
        )
        is False
    )
    assert calls == []

    # Pure plan for uniform still classifies while forced-off (no side effects).
    uniform_plan = classify_config_apply_plan(
        configured_effect="static",
        current=ConfigApplyState(
            effect="static",
            selected_effect="static",
            speed=4,
            brightness=22,
            color=(255, 10, 10),
            perkey_sig=(),
            reactive_use_manual=False,
            reactive_color=(255, 255, 255),
            secondary_sig=(
                ("logo", (("enabled", True), ("color", (255, 10, 10)))),
                ("neon", (("enabled", True), ("color", (10, 255, 10)))),
            ),
        ),
    )
    assert uniform_plan.execution_kind == "apply"
    assert uniform_plan.apply_mode in {"uniform", "effect", "perkey"}

    secondary_sig = (
        ("logo", (("enabled", True), ("color", (255, 10, 10)))),
        ("neon", (("enabled", True), ("color", (10, 255, 10)))),
    )
    effect_plan = classify_config_apply_plan(
        configured_effect="wave",
        current=ConfigApplyState(
            effect="wave",
            selected_effect="wave",
            speed=5,
            brightness=22,
            color=(0, 0, 0),
            perkey_sig=(),
            reactive_use_manual=False,
            reactive_color=(255, 255, 255),
            secondary_sig=secondary_sig,
        ),
    )
    assert effect_plan.execution_kind == "apply"
    assert effect_plan.apply_mode == "effect"

    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=False
    )
    tray.is_off = False

    ok = apply_secondary_static_scene(
        tray,
        payload=payload,
        effective_routes_fn=lambda: tuple(_effective(r) for r in tray._routes),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )
    assert ok is True
    assert any(c[0] == "logo" and c[1] == "set_color" for c in calls)
    assert any(c[0] == "neon" and c[1] == "set_color" for c in calls)
