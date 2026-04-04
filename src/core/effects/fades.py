from __future__ import annotations

import time
from collections.abc import Mapping
from threading import RLock
from typing import Any, Tuple

from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
)
from src.core.effects.transitions import (
    avoid_full_black,
    choose_steps,
    scaled_color_map_nonzero,
)


_FADE_SETUP_ERRORS = (IndexError, OverflowError, TypeError, ValueError)
_FADE_RUNTIME_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


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
        duration = float(duration_s)
        fr, fg, fb = (int(from_color[0]), int(from_color[1]), int(from_color[2]))
        tr, tg, tb = (int(to_color[0]), int(to_color[1]), int(to_color[2]))
        brightness_hw = max(0, min(50, int(brightness)))
        max_steps = int(steps)
    except _FADE_SETUP_ERRORS:
        return

    if duration <= 0:
        steps = 1
        dt = 0.0
    else:
        try:
            steps = choose_steps(duration_s=duration, max_steps=max_steps)
        except _FADE_SETUP_ERRORS:
            return
        dt = duration / float(steps)

    # Avoid brightness 0 during transitions (tray/hardware pollers may interpret it as "off").
    effective_brightness = max(1, brightness_hw) if brightness_hw > 0 else 0

    # Ensure we are in software/user mode before attempting uniform writes.
    enable_user_mode_once(kb=kb, kb_lock=kb_lock, brightness=effective_brightness)

    for i in range(1, steps + 1):
        t = float(i) / float(steps)
        r = int(round(fr + (tr - fr) * t))
        g = int(round(fg + (tg - fg) * t))
        b = int(round(fb + (tb - fb) * t))

        try:
            r, g, b = avoid_full_black(
                rgb=(r, g, b),
                target_rgb=(tr, tg, tb),
                brightness=effective_brightness,
            )
            with kb_lock:
                kb.set_color((r, g, b), brightness=effective_brightness)
        except _FADE_RUNTIME_ERRORS:
            return
        if dt > 0:
            time.sleep(dt)


def fade_in_per_key(
    *,
    kb: Any,
    kb_lock: RLock,
    per_key_colors: Mapping[Tuple[int, int], Tuple[int, int, int]] | None,
    current_color: tuple,
    brightness: int,
    duration_s: float,
    steps: int = 12,
) -> None:
    """Fade in the current per-key map to reduce harsh transitions."""

    if not per_key_colors:
        return

    try:
        duration = float(duration_s)
    except _FADE_SETUP_ERRORS:
        return

    if duration <= 0:
        return

    try:
        steps = choose_steps(
            duration_s=duration,
            max_steps=int(steps),
            target_fps=50.0,
            min_dt_s=0.012,
        )
        base_color_src = current_color or (255, 0, 0)
        base_color = (
            int(base_color_src[0]),
            int(base_color_src[1]),
            int(base_color_src[2]),
        )
        brightness_hw = int(brightness)
        full_colors = build_full_color_grid(
            base_color=base_color,
            per_key_colors=per_key_colors,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )
    except _FADE_SETUP_ERRORS:
        return

    dt = duration / float(steps)

    enable_user_mode_once(kb=kb, kb_lock=kb_lock, brightness=brightness_hw)

    for i in range(1, steps + 1):
        scale = float(i) / float(steps)
        try:
            color_map = scaled_color_map_nonzero(full_colors, scale=scale, brightness=brightness_hw)
            with kb_lock:
                kb.set_key_colors(color_map, brightness=brightness_hw, enable_user_mode=False)
        except _FADE_RUNTIME_ERRORS:
            return
        time.sleep(dt)
