from __future__ import annotations

import logging
from threading import RLock
from typing import Any, Callable, Dict, Optional

from src.core.utils.logging_utils import log_throttled


def _hw_speed_from_ui_speed(ui_speed: int, *, kb: Any) -> int:
    policy = str(getattr(kb, "keyrgb_hw_speed_policy", "direct") or "direct").strip().lower()
    normalized = max(0, min(10, int(ui_speed)))
    if policy == "inverted":
        return max(0, min(10, 11 - normalized))
    return normalized


def allowed_hw_effect_keys(effect_func: Callable[..., Any], *, logger: logging.Logger) -> set[str]:
    """Best-effort introspection of ite8291r3-ctl's effect builders."""

    try:
        freevars = getattr(effect_func, "__code__").co_freevars
        closure = getattr(effect_func, "__closure__")
        if not freevars or not closure:
            return set()
        mapping = dict(zip(freevars, [c.cell_contents for c in closure]))
        args = mapping.get("args")
        if isinstance(args, dict):
            return set(args.keys())
    except Exception as exc:
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
    effect_func: Callable[..., Any],
    ui_speed: int,
    brightness: int,
    current_color: tuple,
    hw_colors: Dict[str, int],
    kb: Any,
    kb_lock: RLock,
    logger: logging.Logger,
    direction: Optional[str] = None,
) -> Any:
    """Build payload for a hardware effect.

    Mirrors the previous logic in EffectsEngine._start_hw_effect (including the
    "drop unsupported keys" retry loop).
    """

    # Hardware speed policy is backend-specific.
    # - ite8910: firmware uses 0..10 with larger values = faster
    # - ite8291r3: vendored backend documents 0 = fastest, 10 = slowest
    # Unknown backends default to the UI scale directly so new hardware-effect
    # paths do not inherit the old inverted behavior by accident.
    hw_speed = _hw_speed_from_ui_speed(ui_speed, kb=kb)

    hw_kwargs: Dict[str, Any] = {
        "speed": hw_speed,
        "brightness": int(brightness),
    }

    allowed = allowed_hw_effect_keys(effect_func, logger=logger)

    # For palette-based backends (hw_colors non-empty), breathing uses a
    # palette slot. For direct-RGB backends (hw_colors empty), pass the
    # user's color as an RGB tuple.
    if effect_name == "breathing" and hw_colors:
        palette_slot = int(hw_colors.get("red", 1))
        try:
            with kb_lock:
                kb.set_palette_color(palette_slot, tuple(current_color))
        except Exception as exc:
            # Hardware writes are a runtime boundary: log full exception
            # context, then continue building the payload as before.
            log_throttled(
                logger,
                "legacy.effects.palette_color",
                interval_s=120,
                level=logging.DEBUG,
                msg="Failed to program palette slot for breathing effect",
                exc=exc,
            )
        hw_kwargs["color"] = palette_slot

    # Direct-RGB color pass-through for backends that accept color as an
    # RGB tuple (ITE8910). Only set if not already populated by the palette
    # path above.
    if "color" not in hw_kwargs and "color" in allowed:
        hw_kwargs["color"] = tuple(current_color)

    if direction and "direction" in allowed:
        hw_kwargs["direction"] = direction

    if allowed:
        hw_kwargs = {k: v for k, v in hw_kwargs.items() if k in allowed}

    last_err: Optional[Exception] = None
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
