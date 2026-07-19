"""Multi-layer: idle dim/restore policy + forced-off bag + secondary static + config plan.

Hardware-free integration covering the seam where idle-power actions, tray idle
state ownership, secondary lighting, and pure config-apply classification meet.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.core.secondary_device_routes import SecondaryDeviceRoute
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.tray.controllers.secondary_static_scene import apply_secondary_static_scene
from src.tray.idle_power_state import (
    is_dim_temp_active,
    set_idle_power_state_field,
)
from src.tray.pollers.config_polling_internal._apply_plan import classify_config_apply_plan
from src.tray.pollers.config_polling_internal.core import ConfigApplyState
from src.tray.pollers.idle_power.policy import compute_idle_action
from src.tray.pollers.idle_power.polling import _apply_idle_action
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


def _mk_engine(*, brightness: int = 25) -> SimpleNamespace:
    writes: list[int] = []

    class _KB:
        def set_brightness(self, value: int) -> None:
            writes.append(int(value))

    return SimpleNamespace(
        kb=_KB(),
        brightness=brightness,
        effect="static",
        is_running=False,
        _brightness_writes=writes,
        set_brightness=lambda value: writes.append(int(value)),
    )


def test_idle_dim_then_restore_updates_owner_bag_and_allows_secondary() -> None:
    logo = _route("logo")
    areas = {"logo": {"enabled": True, "color": [255, 0, 0]}}
    engine = _mk_engine(brightness=25)
    tray = make_owner_backed_simple_tray(
        is_off=False,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        config=SimpleNamespace(
            brightness=25,
            effect="static",
            screen_dim_sync_mode="temp",
            screen_dim_temp_brightness=5,
            _settings={"secondary_device_state": areas},
        ),
        engine=engine,
        _routes=(logo,),
    )

    action = compute_idle_action(
        dimmed=True,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=False,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=False,
        power_forced_off=False,
        now=100.0,
        last_idle_turn_off_at=0.0,
        last_resume_at=0.0,
    )
    assert action == "dim_to_temp"

    _apply_idle_action(tray, action="dim_to_temp", dim_temp_brightness=5)
    assert is_dim_temp_active(tray) is True
    assert tray.tray_idle_power_state.dim_temp_active is True

    # Forced-off during dim must block secondary static apply.
    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=True
    )
    secondary_calls: list[tuple[str, str]] = []
    assert (
        apply_secondary_static_scene(
            tray,
            payload={"version": 1, "areas": areas},
            effective_routes_fn=lambda: tuple(_effective(r) for r in tray._routes),
            acquire_device_fn=lambda route: _Device(route.state_key, secondary_calls),
        )
        is False
    )
    assert secondary_calls == []

    set_idle_power_state_field(
        tray, attr_name="_power_forced_off", state_name="power_forced_off", value=False
    )

    restore = compute_idle_action(
        dimmed=False,
        screen_off=False,
        is_off=False,
        idle_forced_off=False,
        dim_temp_active=True,
        idle_timeout_s=60.0,
        power_management_enabled=True,
        screen_dim_sync_enabled=True,
        screen_dim_sync_mode="temp",
        screen_dim_temp_brightness=5,
        brightness=25,
        user_forced_off=False,
        power_forced_off=False,
        now=105.0,
        last_idle_turn_off_at=0.0,
        last_resume_at=0.0,
    )
    assert restore == "restore_brightness"

    _apply_idle_action(tray, action="restore_brightness", dim_temp_brightness=5)
    assert is_dim_temp_active(tray) is False

    ok = apply_secondary_static_scene(
        tray,
        payload={"version": 1, "areas": areas},
        effective_routes_fn=lambda: tuple(_effective(r) for r in tray._routes),
        acquire_device_fn=lambda route: _Device(route.state_key, secondary_calls),
    )
    assert ok is True
    assert ("logo", "set_color") in secondary_calls

    plan = classify_config_apply_plan(
        configured_effect="static",
        current=ConfigApplyState(
            effect="static",
            selected_effect="static",
            speed=3,
            brightness=25,
            color=(10, 20, 30),
            perkey_sig=(),
            reactive_use_manual=False,
            reactive_color=(255, 255, 255),
            secondary_sig=(("logo", (("enabled", True), ("color", (255, 0, 0)))),),
        ),
    )
    assert plan.execution_kind == "apply"
    assert plan.apply_mode in {"uniform", "effect", "perkey"}


def test_uniform_config_plan_with_secondary_while_not_forced_off() -> None:
    """Config-apply classification for uniform mode stays pure beside secondary apply."""
    logo = _route("logo")
    neon = _route("neon")
    areas = {
        "logo": {"enabled": True, "color": [1, 2, 3]},
        "neon": {"enabled": False, "color": [4, 5, 6]},
    }
    tray = make_owner_backed_simple_tray(
        is_off=False,
        power_forced_off=False,
        user_forced_off=False,
        idle_forced_off=False,
        config=SimpleNamespace(_settings={"secondary_device_state": areas}),
        _routes=(logo, neon),
    )
    calls: list[tuple[str, str]] = []

    ok = apply_secondary_static_scene(
        tray,
        payload={"version": 1, "areas": areas},
        effective_routes_fn=lambda: tuple(_effective(r) for r in tray._routes),
        acquire_device_fn=lambda route: _Device(route.state_key, calls),
    )
    assert ok is True
    assert ("logo", "set_color") in calls
    # Disabled neon should not receive set_color (turn_off or skip depending on policy).
    assert ("neon", "set_color") not in calls

    plan = classify_config_apply_plan(
        configured_effect="static",
        current=ConfigApplyState(
            effect="static",
            selected_effect="static",
            speed=2,
            brightness=30,
            color=(100, 100, 100),
            perkey_sig=(),
            reactive_use_manual=False,
            reactive_color=(255, 255, 255),
            secondary_sig=(
                ("logo", (("enabled", True), ("color", (1, 2, 3)))),
                ("neon", (("enabled", False), ("color", (4, 5, 6)))),
            ),
        ),
    )
    assert plan.execution_kind == "apply"
    assert plan.apply_mode in {"uniform", "effect", "perkey"}
