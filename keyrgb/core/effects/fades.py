from __future__ import annotations

import time
from collections.abc import Mapping
from threading import RLock

from keyrgb.core.effects.device import KeyboardDeviceProtocol
from keyrgb.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from keyrgb.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
)
from keyrgb.core.effects.transitions import (
    avoid_full_black,
    choose_steps,
    scaled_color_map_nonzero,
)

_FADE_SETUP_ERRORS = (IndexError, OverflowError, TypeError, ValueError)
_FADE_RUNTIME_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

Color = tuple[int, int, int]
Key = tuple[int, int]


def fade_uniform_color(
    *,
    kb: KeyboardDeviceProtocol,
    kb_lock: RLock,
    from_color: Color,
    to_color: Color,
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
        r = round(fr + (tr - fr) * t)
        g = round(fg + (tg - fg) * t)
        b = round(fb + (tb - fb) * t)

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


def prime_per_key_frame(
    *,
    kb: KeyboardDeviceProtocol,
    kb_lock: RLock,
    per_key_colors: Mapping[Key, Color] | None,
    current_color: Color,
    brightness: int,
    reassert_user_mode: bool = False,
    num_rows: int = NUM_ROWS,
    num_cols: int = NUM_COLS,
) -> bool:
    """Write the final per-key frame once without a startup fade.

    Row data is programmed before brightness is raised.  This avoids the
    controller-visible full-deck initialization flash that otherwise appears
    when KeyRGB starts or reclaims an ITE controller after firmware sleep.

    Pass ``reassert_user_mode=True`` when the controller was explicitly
    switched out of user mode (``turn_off`` effect command): row and
    brightness writes alone leave the deck dark until a mode command
    re-enables user mode.  A fresh process cannot know whether firmware
    retained that off mode, so an ordinary prime verifies the resulting state
    and re-enables user mode only when the controller is still off.
    """

    if not per_key_colors:
        return False

    try:
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
            num_rows=int(num_rows),
            num_cols=int(num_cols),
        )
    except _FADE_SETUP_ERRORS:
        return False

    try:
        with kb_lock:
            kb.set_key_colors(full_colors, brightness=brightness_hw, enable_user_mode=bool(reassert_user_mode))
            set_brightness = getattr(kb, "set_brightness", None)
            if callable(set_brightness):
                set_brightness(brightness_hw)
            if not reassert_user_mode:
                # Explicit off mode (is_off) *or* firmware sleep signature
                # (brightness still 0 with is_off=False) — both need a mode
                # command; row/brightness writes alone leave ITE decks dark.
                still_dark = bool(kb.is_off())
                if not still_dark:
                    get_brightness = getattr(kb, "get_brightness", None)
                    if callable(get_brightness):
                        try:
                            still_dark = int(get_brightness()) <= 0
                        except _FADE_RUNTIME_ERRORS:
                            still_dark = False
                if still_dark:
                    enable_user_mode = getattr(kb, "enable_user_mode", None)
                    if not callable(enable_user_mode):
                        return False
                    enable_user_mode(brightness=brightness_hw, save=False)
    except _FADE_RUNTIME_ERRORS:
        return False
    return True


def fade_in_per_key(
    *,
    kb: KeyboardDeviceProtocol,
    kb_lock: RLock,
    per_key_colors: Mapping[Key, Color] | None,
    current_color: Color,
    brightness: int,
    duration_s: float,
    steps: int = 12,
    num_rows: int = NUM_ROWS,
    num_cols: int = NUM_COLS,
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
            num_rows=int(num_rows),
            num_cols=int(num_cols),
        )
    except _FADE_SETUP_ERRORS:
        return

    dt = duration / float(steps)

    enable_user_mode_once(kb=kb, kb_lock=kb_lock, brightness=brightness_hw, save=True)

    for i in range(1, steps + 1):
        scale = float(i) / float(steps)
        try:
            color_map = scaled_color_map_nonzero(full_colors, scale=scale, brightness=brightness_hw)
            with kb_lock:
                kb.set_key_colors(color_map, brightness=brightness_hw, enable_user_mode=False)
        except _FADE_RUNTIME_ERRORS:
            return
        time.sleep(dt)
