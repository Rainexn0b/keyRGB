from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Tuple

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
)
from src.core.effects.transitions import avoid_full_black
from src.core.utils.logging_utils import log_throttled
from src.core.utils.exceptions import is_device_disconnected

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def mix(a: Color, b: Color, t: float) -> Color:
    tt = clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * tt)),
        int(round(a[1] + (b[1] - a[1]) * tt)),
        int(round(a[2] + (b[2] - a[2]) * tt)),
    )


def scale(rgb: Color, s: float) -> Color:
    ss = clamp01(s)
    return (int(round(rgb[0] * ss)), int(round(rgb[1] * ss)), int(round(rgb[2] * ss)))


def _resolve_brightness(engine: "EffectsEngine") -> Tuple[int, int, int]:
    """Resolve brightness levels for mixed-content rendering.

    Returns (base_hw, effect_hw, global_hw).
    """
    # Pulse/highlight target brightness for reactive effects.
    # This is separate from the hardware brightness (`engine.brightness`).
    try:
        eff = int(getattr(engine, "reactive_brightness", getattr(engine, "brightness", 25)) or 0)
    except Exception:
        eff = 25
    eff = max(0, min(50, eff))

    # Hardware brightness cap (policies dim/undim this).
    try:
        global_hw = int(getattr(engine, "brightness", 25) or 0)
    except Exception:
        global_hw = 25
    global_hw = max(0, min(50, global_hw))

    base = 0
    try:
        if getattr(engine, "per_key_colors", None):
            base = int(getattr(engine, "per_key_brightness", 0) or 0)
    except Exception:
        pass
    base = max(0, min(50, base))

    # Treat `engine.brightness` as a global cap for reactive rendering.
    #
    # Historically we used `global_hw = max(base, eff)` so either channel could
    # drive the hardware brightness upward and we would scale the other channel
    # down. In practice, users often set per-key backdrop brightness high for
    # reactive typing, and then policy-driven dim/undim would momentarily jump
    # the hardware brightness to 100% (visible flash) even when the selected
    # profile brightness is low.
    #
    # Keeping the hardware brightness capped to `global_hw` prevents flashes and
    # makes dim/undim transitions stable.
    return base, eff, global_hw


def backdrop_brightness_scale_factor(engine: "EffectsEngine", *, effect_brightness_hw: int) -> float:
    """Compute scaling factor to keep the backdrop at its target brightness.

    If the global hardware brightness is driven higher (by the effect brightness),
    we scale the backdrop down.
    """
    base, _, global_hw = _resolve_brightness(engine)

    if global_hw <= 0:
        return 0.0

    if base >= global_hw:
        return 1.0

    return float(base) / float(global_hw)


def pulse_brightness_scale_factor(engine: "EffectsEngine") -> float:
    """Compute scaling factor to keep pulses at their target brightness.

    If the global hardware brightness is driven higher (by the base brightness),
    we scale the pulses down.
    """
    _, eff, global_hw = _resolve_brightness(engine)

    if global_hw <= 0:
        return 0.0

    if eff >= global_hw:
        return 1.0

    return float(eff) / float(global_hw)


def apply_backdrop_brightness_scale(color_map: Dict[Key, Color], *, factor: float) -> Dict[Key, Color]:
    """Return a scaled copy of a per-key base map."""

    f = float(factor)
    if f >= 0.999:
        return dict(color_map)
    if f <= 0.0:
        return {k: (0, 0, 0) for k in color_map.keys()}
    return {k: scale(rgb, f) for k, rgb in color_map.items()}


def frame_dt_s() -> float:
    return 1.0 / 60.0


def pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Matches the quadratic mapping used by the SW loops: speed=10 is much faster.
    """

    try:
        s = int(getattr(engine, "speed", 4) or 0)
    except Exception:
        s = 4

    s = max(0, min(10, s))
    t = float(s) / 10.0
    t = t * t

    min_factor = float(min_factor)
    max_factor = float(max_factor)
    if min_factor == 0.8 and max_factor == 2.2:
        min_factor = 0.25
        max_factor = 10.0

    return float(min_factor + (max_factor - min_factor) * t)


def has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(engine.kb, "set_key_colors", None))


def base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (
        int(base_color_src[0]),
        int(base_color_src[1]),
        int(base_color_src[2]),
    )

    per_key = getattr(engine, "per_key_colors", None) or None
    if not per_key:
        return {(r, c): base_color for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    full = build_full_color_grid(
        base_color=base_color,
        per_key_colors=per_key,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )

    out: Dict[Key, Color] = {}
    for (r, c), rgb in full.items():
        out[(r, c)] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    return out


def render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    # Determine proper hardware brightness scaling. Keep resolution under the
    # same lock used by device I/O so a tray-initiated dim/restore can't race
    # a frame and produce a one-frame stale brightness write.

    if has_per_key(engine):
        try:
            with engine.kb_lock:
                _, _, brightness_hw = _resolve_brightness(engine)
                enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw))
                try:
                    engine.kb.set_key_colors(color_map, brightness=int(brightness_hw), enable_user_mode=False)
                    return
                except Exception as exc:
                    if is_device_disconnected(exc):
                        try:
                            engine.mark_device_unavailable()
                        except Exception:
                            pass
                        return
                    raise
        except Exception as exc:
            log_throttled(
                logger,
                "effects.render.per_key_failed",
                interval_s=30,
                level=logging.WARNING,
                msg="Per-key render failed; falling back to uniform",
                exc=exc,
            )

    if not color_map:
        rgb = (0, 0, 0)
    else:
        rs = sum(c[0] for c in color_map.values())
        gs = sum(c[1] for c in color_map.values())
        bs = sum(c[2] for c in color_map.values())
        n = max(1, len(color_map))
        rgb = (int(rs / n), int(gs / n), int(bs / n))

    with engine.kb_lock:
        _, _, brightness_hw = _resolve_brightness(engine)
        r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(brightness_hw))
        enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(brightness_hw))
        engine.kb.set_color((r, g, b), brightness=int(brightness_hw))
