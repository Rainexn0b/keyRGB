from __future__ import annotations

from keyrgb.core.effects.catalog import (
    REACTIVE_EFFECTS,
    SOFTWARE_EFFECTS,
    SW_EFFECTS,
    title_for_effect,
)
from keyrgb.core.effects.effect_contract import CURRENT_COLOR, EffectKind
from keyrgb.core.effects.registry import (
    _invalidate_discovery_cache,
    discover_effect_registrations,
    get_effect_registration,
)
from keyrgb.core.effects.software import effects as software_effects


def test_shipped_software_and_reactive_effects_are_discovered_in_catalog_order() -> None:
    _invalidate_discovery_cache()
    registrations = discover_effect_registrations()

    assert SOFTWARE_EFFECTS == [
        "rainbow_wave",
        "rainbow_swirl",
        "spectrum_cycle",
        "color_cycle",
        "chase",
        "twinkle",
        "strobe",
        "breathing",
        "fire",
        "rain",
        "random",
    ]
    assert REACTIVE_EFFECTS == ["reactive_fade", "reactive_ripple"]
    assert SW_EFFECTS == [*SOFTWARE_EFFECTS, *REACTIVE_EFFECTS]
    assert [item.name for item in registrations] == SW_EFFECTS
    assert [item.kind for item in registrations if item.name in SOFTWARE_EFFECTS] == [EffectKind.SOFTWARE] * len(
        SOFTWARE_EFFECTS
    )


def test_promoted_software_runners_are_registered() -> None:
    _invalidate_discovery_cache()
    names = {item.name for item in discover_effect_registrations()}

    assert {"breathing", "fire", "rain", "random"} <= names
    assert callable(software_effects.run_breathing)
    assert callable(software_effects.run_fire)
    assert callable(software_effects.run_rain)
    assert callable(software_effects.run_random)


def test_registration_start_colors_and_titles_match_shipped_behavior() -> None:
    _invalidate_discovery_cache()

    rainbow = get_effect_registration("rainbow_wave")
    chase = get_effect_registration("chase")
    fade = get_effect_registration("reactive_fade")

    assert rainbow is not None
    assert rainbow.start_color == (255, 0, 0)
    assert chase is not None
    assert chase.start_color == CURRENT_COLOR
    assert fade is not None
    assert fade.start_color == CURRENT_COLOR
    assert title_for_effect("reactive_fade") == "Reactive Typing (Fade)"
    assert title_for_effect("reactive_ripple") == "Reactive Typing (Ripple)"
    assert title_for_effect("rainbow_wave") == "Rainbow Wave"
    assert title_for_effect("chase") == "Chase"
    breathing = get_effect_registration("breathing")
    rain = get_effect_registration("rain")
    assert breathing is not None
    assert breathing.start_color == CURRENT_COLOR
    assert rain is not None
    assert rain.start_color == CURRENT_COLOR
    assert title_for_effect("breathing") == "Breathing"
    assert title_for_effect("fire") == "Fire"
