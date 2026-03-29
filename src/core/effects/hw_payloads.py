from __future__ import annotations

import logging
from threading import RLock
from typing import Any, Dict, Optional

from src.core.backends.base import HardwareEffectDescriptor
from src.core.utils.logging_utils import log_throttled


def allowed_hw_effect_keys(effect_entry: HardwareEffectDescriptor, *, logger: logging.Logger) -> set[str]:
    """Return the supported kwargs advertised by a typed effect descriptor."""

    _ = logger
    return set(effect_entry.supported_args)


def build_hw_effect_payload(
    *,
    effect_name: str,
    effect_func: HardwareEffectDescriptor,
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

    # The controller's speed scale is inverted compared to the UX:
    # UI: 10 = fastest, 0/1 = slowest
    # HW: larger values slow the effect down
    hw_speed = max(0, min(10, 11 - int(ui_speed)))
    effect_builder = effect_func.build

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
        except Exception:
            log_throttled(
                logger,
                "legacy.effects.palette_color",
                interval_s=120,
                level=logging.DEBUG,
                msg="Failed to program palette slot for breathing effect",
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
            return effect_builder(**hw_kwargs)
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
