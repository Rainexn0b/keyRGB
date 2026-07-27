from __future__ import annotations

from src.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT, SecondaryDeviceRoute
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.gui.perkey.secondary_lighting import SecondaryLightingDraft


def _effective(
    state_key: str,
    *,
    available: bool = True,
    simulated: bool = True,
    brightness_policy: str | None = None,
) -> EffectiveSecondaryRoute:
    route = SecondaryDeviceRoute(
        device_type=state_key,
        backend_name=f"backend-{state_key}",
        display_name=state_key.title(),
        state_key=state_key,
        get_backend=lambda: object(),
        get_device=lambda: object(),
        supports_profile_state=True,
        **({"brightness_policy": brightness_policy} if brightness_policy is not None else {}),
    )
    return EffectiveSecondaryRoute(
        route=route,
        available=available,
        simulated=simulated,
        availability_source="simulation" if simulated else "backend_probe",
    )


def test_draft_exposes_injected_inventory_and_updates_profile_payload() -> None:
    draft = SecondaryLightingDraft(
        {"version": 1, "areas": {"mouse": {"enabled": False, "color": [1, 2, 3]}}},
        effective_routes=(_effective("mouse"), _effective("lightbar")),
    )

    areas = draft.areas()
    assert [area.state_key for area in areas] == ["mouse", "lightbar"]
    assert areas[0].enabled is False
    assert areas[0].color == (1, 2, 3)
    assert areas[1].enabled is False

    draft.set_enabled("lightbar", False)
    assert draft.set_color("mouse", (300, -2, "7")) == (255, 0, 7)
    assert draft.payload["areas"] == {
        "mouse": {"enabled": False, "color": [255, 0, 7]},
        "lightbar": {"enabled": False, "color": [255, 0, 0]},
    }


def test_draft_retains_saved_unavailable_area() -> None:
    draft = SecondaryLightingDraft(
        {"version": 1, "areas": {"gone": {"enabled": True, "color": [9, 8, 7]}}},
        effective_routes=(_effective("gone", available=False, simulated=False),),
    )

    area = draft.areas()[0]
    assert area.available is False
    assert area.enabled is True
    assert area.color == (9, 8, 7)
    assert draft.payload["areas"] == {"gone": {"enabled": True, "color": [9, 8, 7]}}


def test_draft_keeps_unknown_top_level_and_entry_fields() -> None:
    draft = SecondaryLightingDraft(
        {
            "version": 4,
            "future": {"preserve": True},
            "areas": {"mouse": {"enabled": True, "vendor": "kept"}},
        },
        effective_routes=(_effective("mouse"),),
    )

    draft.set_color("mouse", (4, 5, 6))
    assert draft.payload == {
        "version": 1,
        "future": {"preserve": True},
        "areas": {"mouse": {"enabled": True, "vendor": "kept", "color": [4, 5, 6]}},
    }


def test_draft_seeds_visible_routes_from_legacy_config_and_preserves_unknown_values() -> None:
    class _Config:
        def get_secondary_device_enabled(self, state_key, *, fallback_keys=(), default=False):
            assert state_key == "lightbar"
            assert fallback_keys == ()
            return True

        def get_secondary_device_color(self, state_key, *, fallback_keys=(), default=(255, 0, 0)):
            assert state_key == "lightbar"
            assert fallback_keys == ()
            return (7, 8, 9)

    draft = SecondaryLightingDraft(
        {"version": 1, "areas": {"future_route": "opaque-future-value"}},
        config=_Config(),
        effective_routes=(_effective("lightbar"),),
    )

    assert draft.payload["areas"] == {
        "future_route": "opaque-future-value",
        "lightbar": {"enabled": True, "color": [7, 8, 9]},
    }


def test_draft_exposes_brightness_only_for_independent_routes() -> None:
    class _Config:
        def get_secondary_device_enabled(self, *_args, **_kwargs):
            return True

        def get_secondary_device_color(self, *_args, **_kwargs):
            return (7, 8, 9)

        def get_secondary_device_brightness(self, *_args, **_kwargs):
            return 30

    draft = SecondaryLightingDraft(
        None,
        config=_Config(),
        effective_routes=(
            _effective("lightbar", brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT),
            _effective("logo"),
        ),
    )

    lightbar, logo = draft.areas()
    assert lightbar.brightness == 30
    assert logo.brightness is None
    assert draft.set_brightness("lightbar", 140) == 100
    assert draft.payload["areas"]["lightbar"]["brightness"] == 100
