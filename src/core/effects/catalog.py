"""Canonical effect catalog.

This module is intentionally dependency-free so it can be imported by both the
core effects engine and the tray UI without circular imports.

It provides:
- canonical effect name lists (ordering matters for UI presentation)
- a stable title mapping for UI labels
- backend-aware helpers for tray/runtime effect resolution
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

HARDWARE_EFFECT_PREFIX: Final[str] = "hw:"


_EFFECT_ALIASES: Final[dict[str, str]] = {}


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

    n = strip_effect_namespace(effect_name)
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

    prefix = ""
    if n.startswith(HARDWARE_EFFECT_PREFIX):
        prefix = HARDWARE_EFFECT_PREFIX
        n = n[len(HARDWARE_EFFECT_PREFIX) :].strip()

    return prefix + _EFFECT_ALIASES.get(n, n)


def is_forced_hardware_effect(effect_name: str) -> bool:
    return str(effect_name or "").strip().lower().startswith(HARDWARE_EFFECT_PREFIX)


def strip_effect_namespace(effect_name: str) -> str:
    normalized = str(effect_name or "").strip().lower()
    if normalized.startswith(HARDWARE_EFFECT_PREFIX):
        return normalized[len(HARDWARE_EFFECT_PREFIX) :].strip()
    return normalized


def detected_backend_hw_effect_names(backend: object | None) -> tuple[str, ...]:
    """Return hardware effect keys exposed by the selected backend only."""

    names: list[str] = []
    effect_fn = getattr(backend, "effects", None) if backend is not None else None
    if callable(effect_fn):
        try:
            raw_effects = effect_fn()
            if isinstance(raw_effects, dict):
                seen: set[str] = set()
                for key in raw_effects.keys():
                    normalized = strip_effect_namespace(normalize_effect_name(str(key or "")))
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        names.append(normalized)
        except Exception:
            names = []

    return tuple(names)


def backend_hw_effect_names(backend: object | None) -> tuple[str, ...]:
    """Return backend hardware effects with a legacy fallback when unknown."""

    detected = detected_backend_hw_effect_names(backend)
    if detected:
        return detected
    return tuple(HW_EFFECTS)


def resolve_effect_name_for_backend(effect_name: str, backend: object | None) -> str:
    """Resolve a configured effect name against the selected backend."""

    normalized = normalize_effect_name(effect_name)
    if not normalized:
        return "none"

    if normalized == "stop":
        return "none"

    if normalized in {"none", "perkey", "hw_uniform", "hardware_uniform"}:
        return normalized

    base_name = strip_effect_namespace(normalized)
    backend_hw = frozenset(backend_hw_effect_names(backend))

    if is_forced_hardware_effect(normalized):
        return base_name if base_name in backend_hw else "none"

    if base_name in SW_EFFECTS_SET and base_name not in backend_hw:
        return base_name

    if base_name in backend_hw:
        return base_name

    if base_name in SW_EFFECTS_SET:
        return base_name

    if base_name in HW_EFFECTS_SET:
        return base_name

    return base_name


def hardware_effect_selection_key(effect_name: str) -> str:
    """Return the stored/menu key for a hardware effect selection."""

    normalized = strip_effect_namespace(normalize_effect_name(effect_name))
    if normalized in SW_EFFECTS_SET:
        return f"{HARDWARE_EFFECT_PREFIX}{normalized}"
    return normalized


def is_backend_hardware_effect(effect_name: str, backend: object | None) -> bool:
    normalized = normalize_effect_name(effect_name)
    base_name = strip_effect_namespace(normalized)
    backend_hw = frozenset(backend_hw_effect_names(backend))

    if is_forced_hardware_effect(normalized):
        return base_name in backend_hw

    return base_name in backend_hw and base_name not in SW_EFFECTS_SET
