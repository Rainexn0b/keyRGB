from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from threading import RLock
from typing import Protocol, cast

from keyrgb.core.backends.effect_contract import (
    HardwareEffectBuilderProtocol,
    UnsupportedHardwareEffectArgument,
)
from keyrgb.core.utils.logging_utils import log_throttled

Color = tuple[int, int, int]


class _PaletteKeyboardProtocol(Protocol):
    def set_palette_color(self, slot: int, color: Color) -> None: ...


class _KeyboardHwSpeedPolicyProtocol(Protocol):
    keyrgb_hw_speed_policy: object


_KNOWN_COLOR_HW_EFFECTS = frozenset({"breathing", "random", "ripple", "raindrop", "aurora", "fireworks"})
_KNOWN_RANDOM_SENTINEL_HW_EFFECTS = frozenset({"random"})
_PALETTE_PROGRAM_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _keyboard_hw_speed_policy_or_default(kb: object, *, default: str) -> str:
    try:
        policy = cast(_KeyboardHwSpeedPolicyProtocol, kb).keyrgb_hw_speed_policy
    except AttributeError:
        return default
    return str(policy or default)


def _hw_speed_from_ui_speed(ui_speed: int, *, kb: object) -> int:
    policy = _keyboard_hw_speed_policy_or_default(kb, default="direct").strip().lower()
    normalized = max(0, min(10, int(ui_speed)))
    if policy == "inverted":
        return max(0, min(10, 11 - normalized))
    return normalized


def allowed_hw_effect_keys(effect_func: Callable[..., object], *, logger: logging.Logger) -> set[str]:
    """Return explicitly declared hardware-effect payload fields.

    ``logger`` remains in the signature for public compatibility. Builders that
    predate the explicit contract return an empty set and are called unchanged.
    """

    del logger
    accepted = getattr(cast(HardwareEffectBuilderProtocol, effect_func), "accepted_kwargs", None)
    if not isinstance(accepted, frozenset) or not all(isinstance(key, str) for key in accepted):
        return set()
    return set(accepted)


def _has_explicit_hw_effect_contract(effect_func: Callable[..., object]) -> bool:
    accepted = getattr(cast(HardwareEffectBuilderProtocol, effect_func), "accepted_kwargs", None)
    return isinstance(accepted, frozenset) and all(isinstance(key, str) for key in accepted)


def build_hw_effect_payload(
    *,
    effect_name: str,
    effect_func: Callable[..., object],
    ui_speed: int,
    brightness: int,
    current_color: Color,
    hw_colors: Mapping[str, int],
    kb: _PaletteKeyboardProtocol,
    kb_lock: RLock,
    logger: logging.Logger,
    direction: str | None = None,
) -> object:
    """Build payload for a hardware effect.

    Builders with explicit metadata are filtered before invocation. Legacy
    builders without metadata receive the common payload fields unchanged.
    """

    # Hardware speed policy is backend-specific.
    # - ite8910_perkey: firmware uses 0..10 with larger values = faster
    # - ite8291r3_perkey: native backend preserves the legacy 0 = fastest, 10 = slowest firmware scale
    # Unknown backends default to the UI scale directly so new hardware-effect
    # paths do not inherit the old inverted behavior by accident.
    hw_speed = _hw_speed_from_ui_speed(ui_speed, kb=kb)

    hw_kwargs: dict[str, object] = {
        "speed": hw_speed,
        "brightness": int(brightness),
    }

    allowed = allowed_hw_effect_keys(effect_func, logger=logger)
    has_explicit_contract = _has_explicit_hw_effect_contract(effect_func)

    normalized_effect_name = str(effect_name or "").strip().lower()
    # Undeclared/plugin builders without metadata receive the historical common
    # fields unchanged. Internal builders publish metadata and are filtered.
    supports_color = (
        not has_explicit_contract or "color" in allowed or normalized_effect_name in _KNOWN_COLOR_HW_EFFECTS
    )

    # Palette-based backends (for example ite8291r3_perkey) expose a firmware color
    # slot table. Any hardware effect that accepts a `color` parameter expects
    # that palette slot index, not a raw RGB tuple.
    if hw_colors and supports_color:
        if normalized_effect_name in _KNOWN_RANDOM_SENTINEL_HW_EFFECTS and "random" in hw_colors:
            hw_kwargs["color"] = int(hw_colors["random"])
        else:
            palette_slot = int(hw_colors.get("red", 1))
            try:
                with kb_lock:
                    kb.set_palette_color(palette_slot, current_color)
            except _PALETTE_PROGRAM_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: set_palette_color is a runtime USB/HID hardware write boundary; recoverable palette programming failures must not block effect payload construction
                # Hardware writes are a runtime boundary: log full exception
                # context, then continue building the payload as before.
                log_throttled(
                    logger,
                    "legacy.effects.palette_color",
                    interval_s=120,
                    level=logging.DEBUG,
                    msg="Failed to program palette slot for hardware effect",
                    exc=exc,
                )
            hw_kwargs["color"] = palette_slot

    # Direct-RGB color pass-through for backends that accept color as an RGB
    # tuple (for example ite8910_perkey). Only set if not already populated by the
    # palette path above.
    if "color" not in hw_kwargs and supports_color:
        hw_kwargs["color"] = tuple(current_color)

    if direction and (not has_explicit_contract or "direction" in allowed):
        hw_kwargs["direction"] = direction

    if has_explicit_contract:
        hw_kwargs = {k: v for k, v in hw_kwargs.items() if k in allowed}

    for _ in range(4):
        try:
            return effect_func(**hw_kwargs)
        except UnsupportedHardwareEffectArgument as exc:
            if exc.argument in hw_kwargs:
                hw_kwargs.pop(exc.argument, None)
                continue
            raise

    raise RuntimeError("Failed to build hardware effect payload")
