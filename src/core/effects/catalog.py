"""Canonical effect catalog.

This module is intentionally dependency-free so it can be imported by both the
core effects engine and the tray UI without circular imports.

It provides:
- canonical software effect name lists (ordering matters for UI presentation)
- a stable title mapping for UI labels
- explicit compatibility handling for older saved hardware effect names
"""

from __future__ import annotations

from typing import Final

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


# Fast membership checks (avoid repeating list->set conversions across modules).
SW_EFFECTS_SET: Final[frozenset[str]] = frozenset(SW_EFFECTS)

HARDWARE_EFFECT_PREFIX: Final[str] = "hw:"


# Compatibility-only migration for older saved hardware effect names that used
# the historical generic catalog instead of backend-owned effect definitions.
LEGACY_EFFECT_NAME_MIGRATIONS: Final[dict[str, str]] = {
    "rainbow": "rainbow_wave",
}

LEGACY_UNSUPPORTED_HARDWARE_EFFECTS: Final[frozenset[str]] = frozenset(
    {
        "breathing",
        "wave",
        "ripple",
        "marquee",
        "raindrop",
        "aurora",
        "fireworks",
    }
)


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
    """Return hardware effect keys exposed by the selected backend only.

    Unlike ``backend_hw_effect_names()``, this does not fall back to the legacy
    generic catalog. It is intended for UI that should reflect actual backend
    detection instead of a best-effort compatibility list.
    """

    names: list[str] = []
    effect_fn = getattr(backend, "effects", None) if backend is not None else None
    if callable(effect_fn):
        try:
            raw_effects = effect_fn()
            if isinstance(raw_effects, dict):
                seen: set[str] = set()
                for key in raw_effects.keys():
                    normalized = normalize_effect_name(str(key or ""))
                    normalized = strip_effect_namespace(normalized)
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        names.append(normalized)
        except Exception:
            names = []

    return tuple(names)


def backend_hw_effect_names(backend: object | None) -> tuple[str, ...]:
    """Return the selected backend's exposed hardware effect keys.

    This is backend-authoritative and does not fall back to the legacy catalog.
    """

    return detected_backend_hw_effect_names(backend)


def resolve_effect_name_for_backend(effect_name: str, backend: object | None) -> str:
    """Resolve a configured effect name against the selected backend.

    This keeps tray/runtime state backend-authoritative while still handling
    legacy saved hardware names from older configs.
    """

    normalized = normalize_effect_name(effect_name)
    if not normalized:
        return "none"

    if normalized == "stop":
        return "none"

    if normalized in {"none", "perkey", "hw_uniform", "hardware_uniform"}:
        return normalized

    backend_hw = frozenset(detected_backend_hw_effect_names(backend))
    base_name = strip_effect_namespace(normalized)

    if is_forced_hardware_effect(normalized):
        return normalized if base_name in backend_hw else "none"

    if base_name in SW_EFFECTS_SET:
        return base_name

    if base_name in backend_hw:
        return base_name

    migrated = LEGACY_EFFECT_NAME_MIGRATIONS.get(base_name)
    if migrated is not None:
        return migrated

    if base_name in LEGACY_UNSUPPORTED_HARDWARE_EFFECTS:
        return "none"

    return base_name


def hardware_effect_selection_key(effect_name: str) -> str:
    """Return the stored/menu key for a hardware effect selection.

    Hardware effects that collide with software names are namespaced so the
    tray can distinguish the user's hardware-vs-software choice.
    """

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
