"""Pure unit tests for effect-route classification."""

from __future__ import annotations

from src.tray.pollers.idle_power._effect_route import (
    EffectRoute,
    apply_to_hardware_for_non_reactive,
    classify_effect_route,
    should_soft_fade_for_turn_off,
)


_REACTIVE = frozenset({"reactive_fade", "reactive_ripple"})
_SW = frozenset({"rainbow_wave", "color_cycle"})


def test_classify_reactive() -> None:
    assert classify_effect_route("reactive_fade", _REACTIVE, _SW) == EffectRoute.REACTIVE


def test_classify_software() -> None:
    assert classify_effect_route("rainbow_wave", _REACTIVE, _SW) == EffectRoute.SOFTWARE


def test_classify_hardware() -> None:
    assert classify_effect_route("rainbow", _REACTIVE, _SW) == EffectRoute.HARDWARE


def test_should_soft_fade_reactive_perkey_no_soft_fade() -> None:
    """Reactive effects on per-key hardware handle their own fade."""
    assert (
        should_soft_fade_for_turn_off(
            route=EffectRoute.REACTIVE,
            engine_supports_perkey=True,
        )
        is False
    )


def test_should_soft_fade_reactive_uniform_uses_soft_fade() -> None:
    """Reactive effects on uniform-only hardware still soft-fade."""
    assert (
        should_soft_fade_for_turn_off(
            route=EffectRoute.REACTIVE,
            engine_supports_perkey=False,
        )
        is True
    )


def test_should_soft_fade_non_reactive_always_soft_fade() -> None:
    """Non-reactive effects always soft-fade regardless of per-key support."""
    assert (
        should_soft_fade_for_turn_off(
            route=EffectRoute.SOFTWARE,
            engine_supports_perkey=True,
        )
        is True
    )
    assert (
        should_soft_fade_for_turn_off(
            route=EffectRoute.HARDWARE,
            engine_supports_perkey=False,
        )
        is True
    )


def test_apply_to_hardware_for_non_reactive() -> None:
    assert apply_to_hardware_for_non_reactive(EffectRoute.HARDWARE) is True
    assert apply_to_hardware_for_non_reactive(EffectRoute.SOFTWARE) is False
    assert apply_to_hardware_for_non_reactive(EffectRoute.REACTIVE) is False
