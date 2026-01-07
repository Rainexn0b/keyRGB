from __future__ import annotations

import logging
from threading import RLock
from typing import Any, Callable, Dict, Optional

from src.core.utils.logging_utils import log_throttled


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
) -> Any:
    """Build payload for a hardware effect.

    Mirrors the previous logic in EffectsEngine._start_hw_effect (including the
    "drop unsupported keys" retry loop).
    """

    # The controller's speed scale is inverted compared to the UX:
    # UI: 10 = fastest, 0/1 = slowest
    # HW: larger values slow the effect down
    hw_speed = max(0, min(10, 11 - int(ui_speed)))

    hw_kwargs: Dict[str, Any] = {
        "speed": hw_speed,
        "brightness": int(brightness),
    }

    # For breathing, use the user's configured RGB.
    # The controller expects a palette index, so we program a palette slot
    # and then reference it.
    if effect_name == "breathing":
        palette_slot = int(hw_colors.get("red", 1))
        try:
            with kb_lock:
                kb.set_palette_color(palette_slot, tuple(current_color))
        except Exception:
            log_throttled(
                logger,
                "legacy.effects.palette_color",
                interval_s=120,
                level=logging.DEBUG,
                msg="Failed to program palette slot for breathing effect",
            )
        hw_kwargs["color"] = palette_slot

    allowed = allowed_hw_effect_keys(effect_func, logger=logger)
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
