"""Parse and cache the ``KEYRGB_EMULATE`` control surface."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

from .compatibility import classify_emulated_names, expand_preset, known_emulation_names, resolve_emulation_name

logger = logging.getLogger(__name__)

EMULATE_ENVIRONMENT_VARIABLE = "KEYRGB_EMULATE"
LEGACY_SIMULATION_ENVIRONMENT_VARIABLE = "KEYRGB_SIMULATE_SECONDARY_DEVICES"
ALL_AUXILIARY_TOKEN = "*"
PRESET_PREFIX = "preset:"
EmulationSource = Literal["emulate", "legacy_secondary_simulate"]

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"", "0", "false", "no", "off"})
_WARNED_BOTH_FLAGS = False


class EmulationError(RuntimeError):
    """Invalid emulation request. Fail closed instead of pretending hardware exists."""


@dataclass(frozen=True)
class EmulationSpec:
    """Canonical emulation request after alias/preset expansion and validation."""

    raw: str
    names: tuple[str, ...]
    primary: str | None
    auxiliary: tuple[str, ...]
    preset: str | None
    source: EmulationSource
    all_auxiliary: bool = False

    def includes_secondary_emulation(self) -> bool:
        return bool(self.all_auxiliary or self.auxiliary or self.primary)


def _flag_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        normalized = str(value).strip().lower()
    except (AttributeError, TypeError, ValueError):
        return False
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return False


def _warn_both_flags() -> None:
    global _WARNED_BOTH_FLAGS
    if _WARNED_BOTH_FLAGS:
        return
    _WARNED_BOTH_FLAGS = True
    logger.warning(
        "%s is set; ignoring legacy %s. Prefer KEYRGB_EMULATE only.",
        EMULATE_ENVIRONMENT_VARIABLE,
        LEGACY_SIMULATION_ENVIRONMENT_VARIABLE,
    )


def _split_tokens(raw: str) -> tuple[str, ...]:
    tokens = tuple(token.strip() for token in raw.split(",") if token.strip())
    if not tokens:
        raise EmulationError(f"{EMULATE_ENVIRONMENT_VARIABLE} is empty after trimming")
    return tokens


def _expand_tokens(tokens: tuple[str, ...]) -> tuple[tuple[str, ...], str | None]:
    if ALL_AUXILIARY_TOKEN in tokens:
        if tokens != (ALL_AUXILIARY_TOKEN,):
            raise EmulationError(f"{ALL_AUXILIARY_TOKEN!r} must be the only {EMULATE_ENVIRONMENT_VARIABLE} token")
        return (ALL_AUXILIARY_TOKEN,), None

    names: list[str] = []
    preset_ids: list[str] = []
    known = known_emulation_names()
    for token in tokens:
        lowered = token.strip().lower()
        if lowered.startswith(PRESET_PREFIX):
            preset_id = lowered[len(PRESET_PREFIX) :].strip()
            names.extend(expand_preset(preset_id))
            preset_ids.append(preset_id)
            continue
        names.append(resolve_emulation_name(token, known=known))

    unique: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        unique.append(name)
    preset = preset_ids[0] if len(preset_ids) == 1 else None
    return tuple(unique), preset


def parse_emulate_spec(
    raw: str | None,
    *,
    source: EmulationSource = "emulate",
) -> EmulationSpec | None:
    """Parse one emulation request.

    Empty or unset values disable emulation. Invalid non-empty values raise
    ``EmulationError`` so callers cannot silently fall back to real hardware.
    """

    if raw is None:
        return None
    trimmed = str(raw).strip()
    if not trimmed:
        return None

    tokens = _split_tokens(trimmed)
    expanded, preset = _expand_tokens(tokens)
    if expanded == (ALL_AUXILIARY_TOKEN,):
        return EmulationSpec(
            raw=trimmed,
            names=(),
            primary=None,
            auxiliary=(),
            preset=preset,
            source=source,
            all_auxiliary=True,
        )

    primary, auxiliary = classify_emulated_names(expanded)
    return EmulationSpec(
        raw=trimmed,
        names=expanded,
        primary=primary,
        auxiliary=auxiliary,
        preset=preset,
        source=source,
        all_auxiliary=False,
    )


def get_emulation_spec() -> EmulationSpec | None:
    """Return the process emulation spec, or ``None`` when emulation is off."""

    raw = os.environ.get(EMULATE_ENVIRONMENT_VARIABLE)
    legacy_enabled = _flag_value(os.environ.get(LEGACY_SIMULATION_ENVIRONMENT_VARIABLE))
    if raw is not None and str(raw).strip():
        if legacy_enabled:
            _warn_both_flags()
        return parse_emulate_spec(raw, source="emulate")
    if legacy_enabled:
        return parse_emulate_spec(ALL_AUXILIARY_TOKEN, source="legacy_secondary_simulate")
    return None


def emulation_enabled() -> bool:
    """Return whether any backend emulation is active."""

    return get_emulation_spec() is not None


def emulation_snapshot() -> dict[str, object]:
    """Diagnostics-friendly snapshot that never raises."""

    try:
        spec = get_emulation_spec()
    except EmulationError as exc:
        return {"active": False, "error": str(exc)}
    if spec is None:
        return {"active": False}
    return {
        "active": True,
        "raw": spec.raw,
        "source": spec.source,
        "preset": spec.preset,
        "primary": spec.primary,
        "auxiliary": list(spec.auxiliary),
        "all_auxiliary": spec.all_auxiliary,
        "names": list(spec.names),
    }
