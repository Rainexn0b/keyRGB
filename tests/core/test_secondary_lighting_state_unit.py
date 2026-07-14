from __future__ import annotations

from types import SimpleNamespace

from src.core import secondary_lighting_state
from src.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)


def _route(key: str, *, policy: str) -> SecondaryDeviceRoute:
    return SecondaryDeviceRoute(
        device_type=key,
        backend_name=f"backend-{key}",
        display_name=key.title(),
        state_key=key,
        get_backend=lambda: object(),
        get_device=lambda: object(),
        config_brightness_attr=f"{key}_brightness",
        config_color_attr=f"{key}_color",
        supports_profile_state=True,
        brightness_policy=policy,
    )


def test_enabled_interpretation_is_shared_across_profile_consumers() -> None:
    payload = {
        "areas": {
            "explicit_on": {"enabled": True, "brightness": 0},
            "explicit_off": {"enabled": False, "brightness": 25},
            "legacy_on": {"brightness": 25},
            "legacy_off": {"brightness": 0},
            "default_on": {"color": [1, 2, 3]},
        }
    }

    assert secondary_lighting_state.enabled_state_keys(payload) == {
        "explicit_on",
        "legacy_on",
        "default_on",
    }


def test_config_fallback_payload_persists_brightness_only_for_independent_routes() -> None:
    lightbar = _route("lightbar", policy=BRIGHTNESS_POLICY_INDEPENDENT)
    logo = _route("logo", policy=BRIGHTNESS_POLICY_PRIMARY_SHARED)
    config = SimpleNamespace(
        brightness=45,
        get_secondary_device_enabled=lambda state_key, **_kwargs: state_key == "lightbar",
        get_secondary_device_color=lambda state_key, **_kwargs: (1, 2, 3) if state_key == "lightbar" else (4, 5, 6),
        get_secondary_device_brightness=lambda *_args, **_kwargs: 30,
    )

    assert secondary_lighting_state.payload_from_config(config, (lightbar, logo)) == {
        "version": 1,
        "areas": {
            "lightbar": {"enabled": True, "color": [1, 2, 3], "brightness": 30},
            "logo": {"enabled": False, "color": [4, 5, 6]},
        },
    }


def test_shared_route_brightness_comes_from_primary_keyboard() -> None:
    logo = _route("logo", policy=BRIGHTNESS_POLICY_PRIMARY_SHARED)
    config = SimpleNamespace(
        brightness=40,
        get_secondary_device_brightness=lambda *_args, **_kwargs: 10,
    )

    assert secondary_lighting_state.config_brightness(config, logo) == 40
