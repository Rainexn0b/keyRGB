from __future__ import annotations

import time
from threading import RLock
from typing import Any, Dict, Tuple

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid, enable_user_mode_once
from src.core.effects.transitions import avoid_full_black, choose_steps, scaled_color_map_nonzero


def fade_uniform_color(
    *,
    kb: Any,
    kb_lock: RLock,
    from_color: tuple,
    to_color: tuple,
    brightness: int,
    duration_s: float,
    steps: int = 18,
) -> None:
    """Small cosmetic fade between uniform colors.

    Best-effort only: never raises, never takes too long.
    """

    try:
        if duration_s <= 0:
            steps = 1
            dt = 0.0
        else:
            steps = choose_steps(duration_s=float(duration_s), max_steps=int(steps))
            dt = float(duration_s) / float(steps)

        fr, fg, fb = (int(from_color[0]), int(from_color[1]), int(from_color[2]))
        tr, tg, tb = (int(to_color[0]), int(to_color[1]), int(to_color[2]))
        brightness = max(0, min(50, int(brightness)))

        # Avoid brightness 0 during transitions (tray/hardware pollers may interpret it as "off").
        effective_brightness = max(1, brightness) if brightness > 0 else 0

        for i in range(1, steps + 1):
            t = float(i) / float(steps)
            r = int(round(fr + (tr - fr) * t))
            g = int(round(fg + (tg - fg) * t))
            b = int(round(fb + (tb - fb) * t))

            r, g, b = avoid_full_black(
                rgb=(r, g, b),
                target_rgb=(tr, tg, tb),
                brightness=effective_brightness,
            )
            with kb_lock:
                kb.set_color((r, g, b), brightness=effective_brightness)
            if dt > 0:
                time.sleep(dt)
    except Exception:
        return


def fade_in_per_key(
    *,
    kb: Any,
    kb_lock: RLock,
    per_key_colors: Dict[Tuple[int, int], Tuple[int, int, int]] | None,
    current_color: tuple,
    brightness: int,
    duration_s: float,
    steps: int = 12,
) -> None:
    """Fade in the current per-key map to reduce harsh transitions."""

    try:
        if duration_s <= 0:
            return
        if not per_key_colors:
            return

        steps = choose_steps(duration_s=float(duration_s), max_steps=int(steps), target_fps=50.0, min_dt_s=0.012)
        dt = float(duration_s) / float(steps)

        base_color_src = current_color or (255, 0, 0)
        base_color = (int(base_color_src[0]), int(base_color_src[1]), int(base_color_src[2]))

        full_colors = build_full_color_grid(
            base_color=base_color,
            per_key_colors=per_key_colors,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )

        enable_user_mode_once(kb=kb, kb_lock=kb_lock, brightness=brightness)

        for i in range(1, steps + 1):
            scale = float(i) / float(steps)
            color_map = scaled_color_map_nonzero(full_colors, scale=scale, brightness=int(brightness))
            with kb_lock:
                kb.set_key_colors(color_map, brightness=int(brightness), enable_user_mode=False)
            time.sleep(dt)
    except Exception:
        return
