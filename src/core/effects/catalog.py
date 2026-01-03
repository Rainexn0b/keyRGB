"""Canonical effect catalog.

This module is intentionally dependency-free so it can be imported by both the
core effects engine and the tray UI without circular imports.

It provides:
- canonical effect name lists (ordering matters for UI presentation)
- a stable title mapping for UI labels
"""

from __future__ import annotations

from typing import Final


# Hardware effects (built into the keyboard/controller firmware)
HW_EFFECTS: Final[list[str]] = [
    "rainbow",
    "breathing",
    "wave",
    "ripple",
    "marquee",
    "raindrop",
    "aurora",
    "fireworks",
]


# Software effects (implemented in Python)
SOFTWARE_EFFECTS: Final[list[str]] = [
    "rainbow_wave",
    "rainbow_swirl",
    "spectrum_cycle",
    "color_cycle",
    "chase",
    "twinkle",
    "strobe",
]


# Reactive typing effects (implemented in Python)
REACTIVE_EFFECTS: Final[list[str]] = [
    "reactive_fade",
    "reactive_ripple",
]


SW_EFFECTS: Final[list[str]] = [*SOFTWARE_EFFECTS, *REACTIVE_EFFECTS]
ALL_EFFECTS: Final[list[str]] = [*HW_EFFECTS, *SW_EFFECTS]


# Fast membership checks (avoid repeating list->set conversions across modules).
HW_EFFECTS_SET: Final[frozenset[str]] = frozenset(HW_EFFECTS)
SW_EFFECTS_SET: Final[frozenset[str]] = frozenset(SW_EFFECTS)
ALL_EFFECTS_SET: Final[frozenset[str]] = frozenset(ALL_EFFECTS)


# Backward-compat effect aliases.
_EFFECT_ALIASES: Final[dict[str, str]] = {
    # reactive_rainbow was merged into reactive_ripple.
    "reactive_rainbow": "reactive_ripple",
    # reactive_snake was removed; map old configs to the closest remaining option.
    "reactive_snake": "reactive_ripple",
    # Legacy per-key animation names -> plain perkey.
    "perkey breathing": "perkey",
    "perkey pulse": "perkey",
    "perkey_breathing": "perkey",
    "perkey_pulse": "perkey",
}


_EFFECT_TITLES: Final[dict[str, str]] = {
    "reactive_fade": "Reactive Typing (Fade)",
    "reactive_ripple": "Reactive Typing (Ripple)",
    "rainbow_wave": "Rainbow Wave",
    "rainbow_swirl": "Rainbow Swirl",
    "spectrum_cycle": "Spectrum Cycle",
    "color_cycle": "Color Cycle",
}


def title_for_effect(effect_name: str) -> str:
    """Return a human-friendly label for an effect name."""

    n = str(effect_name or "").strip().lower()
    if not n:
        return ""

    if n in _EFFECT_TITLES:
        return _EFFECT_TITLES[n]

    return n.replace("_", " ").strip().title()


def normalize_effect_name(effect_name: str) -> str:
    """Normalize an effect name into the canonical key.

    This is used for backward compatibility (old config values) and for
    normalizing user input.
    """

    n = str(effect_name or "").strip().lower()
    if not n:
        return ""

    return _EFFECT_ALIASES.get(n, n)
