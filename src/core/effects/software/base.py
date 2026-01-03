from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Tuple

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid, enable_user_mode_once
from src.core.effects.transitions import avoid_full_black
from src.core.logging_utils import log_throttled

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Uses a quadratic curve so the top end (speed=10) is significantly faster.
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


def frame_dt_s() -> float:
    return 1.0 / 60.0


def has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(engine.kb, "set_key_colors", None))


def base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (int(base_color_src[0]), int(base_color_src[1]), int(base_color_src[2]))

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


def render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    """Render per-key when available, otherwise fall back to uniform."""

    if has_per_key(engine):
        try:
            enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_key_colors(color_map, brightness=int(engine.brightness), enable_user_mode=False)
            return
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

    r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
    with engine.kb_lock:
        enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(engine.brightness))
        engine.kb.set_color((r, g, b), brightness=int(engine.brightness))
