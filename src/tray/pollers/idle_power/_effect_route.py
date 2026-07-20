"""Pure effect-route classification for idle-power transitions.

Eliminates duplicated ``effect in reactive_effects_set`` / ``sw_effects_set``
inline branches across ``_action_execution._execute_turn_off``,
``_transition_actions.apply_dim_temp_brightness``, and
``apply_restore_brightness``.
"""

from __future__ import annotations

from enum import Enum


class EffectRoute(str, Enum):
    """Which execution route an effect should take during idle transitions."""

    REACTIVE = "reactive"
    SOFTWARE = "software"
    HARDWARE = "hardware"


def classify_effect_route(
    effect: str,
    reactive_set: frozenset[str],
    sw_set: frozenset[str],
) -> EffectRoute:
    """Classify an effect name into the execution route it belongs to.

    Reactive effects get their own transition path (reactive_lock,
    pulse_hw_lift suppression, restore-seed windows). Software effects
    skip hardware writes. Hardware effects write to the device directly.
    """
    if effect in reactive_set:
        return EffectRoute.REACTIVE
    if effect in sw_set:
        return EffectRoute.SOFTWARE
    return EffectRoute.HARDWARE


def should_soft_fade_for_turn_off(
    *,
    route: EffectRoute,
    engine_supports_perkey: bool,
) -> bool:
    """Whether a soft fade should be used when turning off during idle.

    Reactive effects with per-key output handle their own fade via the
    reactive render loop; a hardware soft-fade would conflict. All other
    combinations use a soft fade for a smooth transition.
    """
    return not (route == EffectRoute.REACTIVE and bool(engine_supports_perkey))


def apply_to_hardware_for_non_reactive(route: EffectRoute) -> bool:
    """Whether a non-reactive brightness write should hit hardware.

    Software effects skip hardware writes (``apply_to_hardware=False``).
    Hardware effects write directly to the device.
    """
    return route == EffectRoute.HARDWARE
