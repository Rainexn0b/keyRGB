from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from threading import RLock
from typing import Protocol, cast

from src.core.utils.logging_utils import log_throttled

Color = tuple[int, int, int]


class _PaletteKeyboardProtocol(Protocol):
    def set_palette_color(self, slot: int, color: Color) -> None: ...


class _KeyboardHwSpeedPolicyProtocol(Protocol):
    keyrgb_hw_speed_policy: object


class _ClosureCodeProtocol(Protocol):
    co_freevars: tuple[str, ...]


class _ClosureCellProtocol(Protocol):
    cell_contents: object


class _ClosureIntrospectableProtocol(Protocol):
    __code__: _ClosureCodeProtocol
    __closure__: tuple[_ClosureCellProtocol, ...] | None


_KNOWN_COLOR_HW_EFFECTS = frozenset({"breathing", "random", "ripple", "raindrop", "aurora", "fireworks"})
_KNOWN_RANDOM_SENTINEL_HW_EFFECTS = frozenset({"random"})
_HW_EFFECT_INTROSPECTION_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
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
    """Best-effort introspection of hardware-effect builder callables."""

    try:
        introspectable = cast(_ClosureIntrospectableProtocol, effect_func)
        freevars = introspectable.__code__.co_freevars
        closure = introspectable.__closure__
        if not freevars or not closure:
            return set()
        mapping = dict(zip(freevars, [c.cell_contents for c in closure]))
        args = mapping.get("args")
        if isinstance(args, dict):
            return set(args.keys())
    except _HW_EFFECT_INTROSPECTION_ERRORS as exc:
        log_throttled(
            logger,
            "legacy.effects.allowed_keys",
            interval_s=120,
            level=logging.DEBUG,
            msg="Failed to introspect hardware effect args",
            exc=exc,
        )
    return set()


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

    Mirrors the previous logic in EffectsEngine._start_hw_effect (including the
    "drop unsupported keys" retry loop).
    """

    # Hardware speed policy is backend-specific.
    # - ite8910: firmware uses 0..10 with larger values = faster
    # - ite8291r3: native backend preserves the legacy 0 = fastest, 10 = slowest firmware scale
    # Unknown backends default to the UI scale directly so new hardware-effect
    # paths do not inherit the old inverted behavior by accident.
    hw_speed = _hw_speed_from_ui_speed(ui_speed, kb=kb)

    hw_kwargs: dict[str, object] = {
        "speed": hw_speed,
        "brightness": int(brightness),
    }

    allowed = allowed_hw_effect_keys(effect_func, logger=logger)

    normalized_effect_name = str(effect_name or "").strip().lower()
    supports_color = "color" in allowed or normalized_effect_name in _KNOWN_COLOR_HW_EFFECTS

    # Palette-based backends (for example ite8291r3) expose a firmware color
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
    # tuple (for example ite8910). Only set if not already populated by the
    # palette path above.
    if "color" not in hw_kwargs and supports_color:
        hw_kwargs["color"] = tuple(current_color)

    if direction and "direction" in allowed:
        hw_kwargs["direction"] = direction

    if allowed:
        hw_kwargs = {k: v for k, v in hw_kwargs.items() if k in allowed}

    last_err: Exception | None = None
    for _ in range(4):
        try:
            return effect_func(**hw_kwargs)
        except ValueError as exc:
            msg = str(exc)
            last_err = exc
            # Expect errors like: "'speed' attr is not needed by effect"
            if "attr is not needed" in msg and msg.startswith("'"):
                bad = msg.split("'", 2)[1]
                if bad in hw_kwargs:
                    hw_kwargs.pop(bad, None)
                    continue
            raise

    raise RuntimeError("Failed to build hardware effect payload") from last_err
