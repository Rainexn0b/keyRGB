"""Persist effect choices while an off-family state owns the deck."""

from __future__ import annotations

from keyrgb.core.effects.catalog import (
    SW_EFFECTS_SET as SW_EFFECTS,
    is_backend_hardware_effect,
    is_forced_hardware_effect,
    strip_effect_namespace,
)
from keyrgb.core.lighting_layers import has_nonempty_per_key_base
from keyrgb.tray.protocols import LightingTrayProtocol


def defer_effect_selection(
    tray: LightingTrayProtocol,
    *,
    effect_name: str,
    per_key_supported: bool,
    hw_effects_supported: bool,
) -> bool:
    """Persist an effect choice without touching the dark deck.

    Effect selection is still normalized and capability-gated while an
    off-family state owns the hardware.  Engine mode attributes are caches,
    so updating them is safe; stopping the engine, starting an effect, and
    writing the keyboard are not.
    """

    from keyrgb.tray.controllers import effect_selection as facade

    if effect_name in {"hw_uniform", "hardware_uniform"}:
        facade._set_attr_best_effort(tray.config, "per_key_colors", {})
        tray.config.effect = "none"
        facade._ensure_hardware_mode(tray)
        return True

    if effect_name in {"none", "stop"}:
        tray.config.effect = "none"
        per_key = facade._config_per_key_colors_ref(tray.config)
        if has_nonempty_per_key_base(per_key) and per_key_supported:
            facade._ensure_software_mode(tray)
        else:
            facade._ensure_hardware_mode(tray)
        return True

    if effect_name == "perkey":
        if not per_key_supported:
            tray.config.effect = "none"
            facade._ensure_hardware_mode(tray)
            return True
        colors = facade._load_per_key_colors_from_profile(tray.config)
        if colors:
            tray.config.per_key_colors = colors
        facade._ensure_software_mode(tray)
        # ``perkey`` is represented by the static per-key map and restored as
        # the normal ``none`` effect by the existing startup path.
        tray.config.effect = "none"
        return True

    base_effect_name = strip_effect_namespace(effect_name)
    if is_backend_hardware_effect(effect_name, getattr(tray, "backend", None)):
        if not hw_effects_supported:
            tray.config.effect = "none"
            facade._ensure_hardware_mode(tray)
            return True
        facade._set_attr_best_effort(tray.config, "per_key_colors", {})
        facade._ensure_hardware_mode(tray)
        tray.config.effect = effect_name if is_forced_hardware_effect(effect_name) else base_effect_name
        return True

    if base_effect_name in SW_EFFECTS and not is_forced_hardware_effect(effect_name):
        facade._ensure_software_mode(tray)
        tray.config.effect = base_effect_name
        return True

    # Unknown selections follow the existing fail-safe normalization, but do
    # not issue the static hardware write until a legal restore.
    tray.config.effect = "none"
    facade._ensure_hardware_mode(tray)
    return True
