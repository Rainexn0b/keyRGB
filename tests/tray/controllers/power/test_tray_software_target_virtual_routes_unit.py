from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.core.secondary_device_routes import BRIGHTNESS_POLICY_PRIMARY_SHARED, iter_virtual_routes
from src.tray.ui import _menu_status_devices


def _make_tray() -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            software_effect_target="all_uniform_capable",
            brightness=25,
            lightbar_brightness=25,
            lightbar_color=(9, 8, 7),
            get_secondary_device_brightness=lambda state_key, *, fallback_keys=(), default=0: 25,
            get_secondary_device_color=lambda state_key, *, fallback_keys=(), default=(255, 0, 0): (255, 0, 0),
            get_secondary_device_enabled=lambda *_args, **_kwargs: True,
        ),
        engine=SimpleNamespace(
            software_effect_target="keyboard",
            secondary_software_targets_provider=None,
            device_available=True,
            _ensure_device_available=lambda: True,
        ),
        backend=None,
        backend_probe=None,
        device_discovery={"candidates": []},
        secondary_device_controls={},
        is_off=False,
        _log_event=MagicMock(),
        _log_exception=MagicMock(),
        _notify_permission_issue=MagicMock(),
    )


def _patch_parent_availability(monkeypatch: pytest.MonkeyPatch, available: bool) -> None:
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


def test_secondary_software_render_targets_include_virtual_routes_when_parent_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.controllers.software_target_controller import secondary_software_render_targets

    _patch_parent_availability(monkeypatch, True)
    tray = _make_tray()

    targets = secondary_software_render_targets(tray)

    keys = {target.key for target in targets}
    assert keys == {"ite8258-chassis-logo", "ite8258-chassis-neon", "ite8258-chassis-vent"}


def test_secondary_software_render_targets_exclude_virtual_routes_when_parent_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.controllers.software_target_controller import secondary_software_render_targets

    _patch_parent_availability(monkeypatch, False)
    tray = _make_tray()

    targets = secondary_software_render_targets(tray)

    assert targets == []


def test_software_effect_target_options_enable_all_mode_with_virtual_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.controllers.software_target_controller import software_effect_target_options

    _patch_parent_availability(monkeypatch, True)
    tray = _make_tray()

    options = software_effect_target_options(tray)

    assert options == [
        {"key": "keyboard", "label": "Keyboard only", "enabled": True},
        {"key": "all_uniform_capable", "label": "Keyboard + enabled lighting areas", "enabled": True},
    ]


def test_cached_secondary_target_set_color_reaches_virtual_zone_device() -> None:
    from src.tray.controllers.software_target_controller import _CachedSecondarySoftwareTarget

    sent: list[tuple[str, tuple[int, int, int], int]] = []

    class DummyZoneDevice:
        def set_color(self, color: object, *, brightness: int) -> None:
            sent.append(("set_color", tuple(color), int(brightness)))  # type: ignore[arg-type]

        def turn_off(self) -> None:
            sent.append(("turn_off",))

    logo_route = next(route for route in iter_virtual_routes() if route.device_type == "logo")
    route = SimpleNamespace(
        device_type=logo_route.device_type,
        get_device=lambda: DummyZoneDevice(),
    )

    target = _CachedSecondarySoftwareTarget(key="ite8258-chassis-logo", route=route)
    target.set_color((0, 255, 0), brightness=25)

    assert sent == [("set_color", (0, 255, 0), 25)]


def test_restore_secondary_software_targets_applies_to_virtual_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core import secondary_device_routes
    from src.tray.controllers import _software_target_auxiliary
    from src.tray.controllers.software_target_controller import restore_secondary_software_targets

    _patch_parent_availability(monkeypatch, True)

    applied: list[tuple[str, str, tuple[int, ...], int]] = []

    class DummyZoneDevice:
        def __init__(self, zone: str) -> None:
            self.zone = zone

        def set_color(self, color: object, *, brightness: int) -> None:
            applied.append((self.zone, "set_color", tuple(color), int(brightness)))  # type: ignore[arg-type]

        def turn_off(self) -> None:
            applied.append((self.zone, "turn_off", (), 0))

    tray = _make_tray()

    original_route_for_context_entry = secondary_device_routes.route_for_context_entry

    def _fake_route_for_context_entry(context_entry: object) -> SimpleNamespace:
        device_type = str(getattr(context_entry, "get", lambda x: "")("device_type"))  # type: ignore[operator]
        if device_type in {"logo", "neon", "vent"}:
            return SimpleNamespace(
                device_type=device_type,
                state_key=f"ite8258_chassis_{device_type}",
                config_brightness_attr=f"ite8258_chassis_{device_type}_brightness",
                config_color_attr=f"ite8258_chassis_{device_type}_color",
                supports_uniform_color=True,
                supports_software_target=True,
                supports_profile_state=True,
                brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
                get_device=lambda zone=device_type: DummyZoneDevice(zone),
            )
        return original_route_for_context_entry(context_entry)  # type: ignore[no-any-return]

    monkeypatch.setattr(secondary_device_routes, "route_for_context_entry", _fake_route_for_context_entry)
    monkeypatch.setattr(_software_target_auxiliary, "route_for_context_entry", _fake_route_for_context_entry)

    restore_secondary_software_targets(tray)

    assert len(applied) == 3
    zones = {entry[0] for entry in applied}
    assert zones == {"logo", "neon", "vent"}
    for entry in applied:
        assert entry[1] == "set_color"


def test_cached_secondary_target_closes_device_on_invalidation() -> None:
    from src.tray.controllers.software_target_controller import _CachedSecondarySoftwareTarget

    close_calls: list[bool] = []

    class DummyZoneDevice:
        def set_color(self, _color: object, *, brightness: int) -> None:
            raise RuntimeError("device failed")

        def turn_off(self) -> None:
            pass

        def close(self) -> None:
            close_calls.append(True)

    route = SimpleNamespace(
        device_type="logo",
        get_device=lambda: DummyZoneDevice(),
    )

    target = _CachedSecondarySoftwareTarget(key="logo", route=route)

    with pytest.raises(RuntimeError, match="device failed"):
        target.set_color((255, 0, 0), brightness=25)

    assert close_calls == [True]
