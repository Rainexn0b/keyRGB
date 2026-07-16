"""Cross-layer Issue #7 regression: mode change + secondary reconcile on c197.

Connects config-mirror authority, real c197 facades, the shared profile
coordinator, and optional output batching without opening real hardware.
"""

from __future__ import annotations

import os
from threading import RLock
from types import SimpleNamespace
from unittest.mock import patch

# Tripwire: any accidental real USB/hidraw open should fail loudly in CI.
os.environ.setdefault("KEYRGB_TEST_HARDWARE_TRIPWIRE", "1")

from src.core.backends.ite8258_perkey_chassis import protocol
from src.core.backends.ite8258_perkey_chassis.device import (
    Ite8258ChassisKeyboardDevice,
    Ite8258ChassisZoneDevice,
)
from src.core.backends.ite8258_perkey_chassis.profile_coordinator import (
    Ite8258ChassisProfileCoordinator,
)
from src.core.secondary_device_routes import SecondaryDeviceRoute, iter_secondary_routes
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.tray.controllers.secondary_static_scene import authoritative_payload_from_config
from src.tray.pollers.config_polling_internal import helpers as polling_helpers


def _route_for(state_key: str) -> SecondaryDeviceRoute:
    for route in iter_secondary_routes():
        if route.state_key == state_key:
            return route
    raise AssertionError(f"missing route {state_key}")


def _effective(route: SecondaryDeviceRoute) -> EffectiveSecondaryRoute:
    return EffectiveSecondaryRoute(
        route=route,
        available=True,
        simulated=True,
        availability_source="integration-test",
    )


def _complete_authoritative_areas(*, logo_enabled: bool = True) -> dict[str, object]:
    chassis_enabled = {
        "ite8258_chassis_logo": logo_enabled,
        "ite8258_chassis_neon": True,
        "ite8258_chassis_vent": True,
    }
    return {
        route.state_key: {
            "enabled": chassis_enabled.get(route.state_key, False),
            "color": [0xAB, 0xCD, 0xEF]
            if route.state_key == "ite8258_chassis_logo"
            else [0x10, 0x20, 0x30]
            if route.state_key == "ite8258_chassis_neon"
            else [0x40, 0x50, 0x60]
            if route.state_key == "ite8258_chassis_vent"
            else [1, 2, 3],
        }
        for route in iter_secondary_routes()
        if route.supports_profile_state
    }


def _build_facades(sent: list[bytes], coordinator: Ite8258ChassisProfileCoordinator) -> dict[str, object]:
    keyboard = Ite8258ChassisKeyboardDevice(sent.append, profile_coordinator=coordinator)
    return {
        "keyboard": keyboard,
        "ite8258_chassis_logo": Ite8258ChassisZoneDevice(
            sent.append,
            zone_name="logo",
            led_ids=protocol.LOGO_LED_IDS,
            profile_coordinator=coordinator,
        ),
        "ite8258_chassis_neon": Ite8258ChassisZoneDevice(
            sent.append,
            zone_name="neon",
            led_ids=protocol.NEON_LED_IDS,
            profile_coordinator=coordinator,
        ),
        "ite8258_chassis_vent": Ite8258ChassisZoneDevice(
            sent.append,
            zone_name="vent",
            led_ids=protocol.VENT_LED_IDS,
            profile_coordinator=coordinator,
        ),
    }


def _legacy_config() -> SimpleNamespace:
    return SimpleNamespace(
        brightness=25,
        _settings={"secondary_device_state": {}},
        get_secondary_device_enabled=lambda state_key, **_kwargs: (
            state_key
            in {
                "ite8258_chassis_logo",
                "ite8258_chassis_neon",
                "ite8258_chassis_vent",
            }
        ),
        get_secondary_device_color=lambda state_key, **_kwargs: (
            (0xAB, 0xCD, 0xEF)
            if state_key == "ite8258_chassis_logo"
            else (0x10, 0x20, 0x30)
            if state_key == "ite8258_chassis_neon"
            else (0x40, 0x50, 0x60)
            if state_key == "ite8258_chassis_vent"
            else (1, 2, 3)
        ),
        get_secondary_device_brightness=lambda *_args, **_kwargs: 25,
    )


def test_empty_and_partial_mirrors_are_not_authoritative() -> None:
    assert authoritative_payload_from_config(SimpleNamespace(_settings={"secondary_device_state": {}})) is None
    assert (
        authoritative_payload_from_config(
            SimpleNamespace(
                _settings={
                    "secondary_device_state": {
                        "ite8258_chassis_logo": {"brightness": 25, "color": [1, 2, 3]},
                    }
                }
            )
        )
        is None
    )


def test_uniform_mode_change_with_legacy_mirror_commits_full_composite_scene_once() -> None:
    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    facades = _build_facades(sent, coordinator)
    keyboard = facades["keyboard"]
    assert isinstance(keyboard, Ite8258ChassisKeyboardDevice)

    logo_route = _route_for("ite8258_chassis_logo")
    neon_route = _route_for("ite8258_chassis_neon")
    vent_route = _route_for("ite8258_chassis_vent")

    tray = SimpleNamespace(
        config=_legacy_config(),
        engine=SimpleNamespace(kb=keyboard, kb_lock=RLock(), stop=lambda: None),
        is_off=False,
        _log_event=lambda *_args, **_kwargs: None,
        _log_exception=lambda *_args, **_kwargs: None,
    )

    def acquire(route: SecondaryDeviceRoute) -> object:
        return facades[route.state_key]

    def reconcile(tray_obj, payload, *, animated: bool) -> None:
        # Inject effective inventory and in-memory devices for the real reconcile path.
        from src.tray.controllers import secondary_static_scene as scene

        if payload is None:
            scene.apply_secondary_static_scene(
                tray_obj,
                effective_routes_fn=lambda: (
                    _effective(logo_route),
                    _effective(neon_route),
                    _effective(vent_route),
                ),
                acquire_device_fn=acquire,
            )
            return
        raise AssertionError(f"expected legacy fallback payload, got {payload!r} (animated={animated})")

    from src.tray.pollers.config_polling_internal import _apply_callbacks

    # Invoke the real config-poller callback. This protects the placement of
    # secondary reconciliation inside the primary output transaction.
    with patch.object(
        polling_helpers._software_target_controller,
        "reconcile_secondary_profile_state",
        new=reconcile,
    ):
        _apply_callbacks._apply_uniform(
            tray,
            SimpleNamespace(color=(0x12, 0x34, 0x56), brightness=25),
            cause="issue7-integration",
        )

    # No controller-global turn-off after the primary write.
    turn_off = protocol.build_turn_off_report()
    assert turn_off not in sent

    expected_groups = (
        *protocol.build_uniform_static_groups((0x12, 0x34, 0x56)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0xAB, 0xCD, 0xEF)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0x10, 0x20, 0x30)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0x40, 0x50, 0x60)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_software_render_batches_primary_and_all_chassis_zones_once() -> None:
    from src.core.effects.software import base as software_base
    from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE

    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    facades = _build_facades(sent, coordinator)
    keyboard = facades["keyboard"]
    assert isinstance(keyboard, Ite8258ChassisKeyboardDevice)

    engine = SimpleNamespace(
        kb=keyboard,
        kb_lock=RLock(),
        brightness=25,
        speed=4,
        current_color=(0x12, 0x34, 0x56),
        per_key_colors=None,
        _last_hw_mode_brightness=25,
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: (
            {"key": "logo", "device_type": "logo", "device": facades["ite8258_chassis_logo"]},
            {"key": "neon", "device_type": "neon", "device": facades["ite8258_chassis_neon"]},
            {"key": "vent", "device_type": "vent", "device": facades["ite8258_chassis_vent"]},
        ),
        mark_device_unavailable=lambda: None,
    )
    rgb = (0x12, 0x34, 0x56)

    software_base.render(engine, color_map={(0, 0): rgb})

    primary_colors = protocol.build_static_led_map({protocol.led_id_from_row_col(0, 0): rgb})
    expected_groups = (
        *protocol.build_static_groups(primary_colors),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, rgb),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, rgb),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, rgb),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]


def test_complete_materialized_mirror_is_authoritative_and_disables_omitted_intent() -> None:
    areas = _complete_authoritative_areas(logo_enabled=False)
    config = SimpleNamespace(
        brightness=25,
        _settings={"secondary_device_state": areas},
        get_secondary_device_enabled=lambda *_a, **_k: True,
        get_secondary_device_color=lambda *_a, **_k: (9, 9, 9),
        get_secondary_device_brightness=lambda *_a, **_k: 99,
    )
    payload = authoritative_payload_from_config(config)
    assert payload == {"version": 1, "areas": areas}

    sent: list[bytes] = []
    coordinator = Ite8258ChassisProfileCoordinator()
    facades = _build_facades(sent, coordinator)
    keyboard = facades["keyboard"]
    assert isinstance(keyboard, Ite8258ChassisKeyboardDevice)

    logo_route = _route_for("ite8258_chassis_logo")
    neon_route = _route_for("ite8258_chassis_neon")
    vent_route = _route_for("ite8258_chassis_vent")

    from src.core.effects.device import optional_output_transaction
    from src.tray.controllers import secondary_static_scene as scene

    tray = SimpleNamespace(config=config, engine=SimpleNamespace(kb=keyboard))

    with optional_output_transaction(keyboard):
        keyboard.set_color((0x12, 0x34, 0x56), brightness=25)
        scene.apply_secondary_static_scene(
            tray,
            payload=payload,
            effective_routes_fn=lambda: (
                _effective(logo_route),
                _effective(neon_route),
                _effective(vent_route),
            ),
            acquire_device_fn=lambda route: facades[route.state_key],
        )

    expected_groups = (
        *protocol.build_uniform_static_groups((0x12, 0x34, 0x56)),
        *protocol.build_uniform_static_groups_for_leds(protocol.LOGO_LED_IDS, (0, 0, 0)),
        *protocol.build_uniform_static_groups_for_leds(protocol.NEON_LED_IDS, (0x10, 0x20, 0x30)),
        *protocol.build_uniform_static_groups_for_leds(protocol.VENT_LED_IDS, (0x40, 0x50, 0x60)),
    )
    assert sent == [
        protocol.build_switch_profile_report(),
        protocol.build_set_direct_mode_report(enabled=False),
        *protocol.build_save_profile_reports(protocol.DEFAULT_PROFILE_ID, expected_groups),
        protocol.build_set_brightness_report(protocol.raw_brightness_from_ui(25)),
    ]
    assert protocol.build_turn_off_report() not in sent
