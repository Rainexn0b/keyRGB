from __future__ import annotations

from typing import Dict, Tuple


def choose_steps(
    *,
    duration_s: float,
    max_steps: int,
    target_fps: float = 45.0,
    min_dt_s: float = 0.015,
) -> int:
    """Choose an interpolation step count with a soft FPS cap.

    Higher steps => smoother, but too many writes can hurt performance.
    """

    if duration_s <= 0:
        return 1

    max_steps = max(1, min(20, int(max_steps)))
    target_fps = max(1.0, float(target_fps))
    min_dt_s = max(0.001, float(min_dt_s))

    # Prefer ~target_fps updates, but don't exceed max_steps.
    steps = int(round(float(duration_s) * target_fps))
    steps = max(2, min(max_steps, steps))

    # Enforce a minimum dt to avoid tight loops.
    dt = float(duration_s) / float(steps)
    if dt < min_dt_s:
        steps = int(float(duration_s) / float(min_dt_s))
        steps = max(2, min(max_steps, steps))

    return steps


def avoid_full_black(
    *,
    rgb: Tuple[int, int, int],
    target_rgb: Tuple[int, int, int],
    brightness: int,
) -> Tuple[int, int, int]:
    """Avoid writing a full-black frame during transitions.

    Some firmware/backends interpret (0,0,0) as "off" and will visually blink
    the keyboard off between effect transitions. If the user actually requested
    black/off, we keep it.
    """

    if int(brightness) <= 0:
        return rgb
    if tuple(target_rgb) == (0, 0, 0):
        return rgb
    if tuple(rgb) != (0, 0, 0):
        return rgb

    tr, tg, tb = (int(target_rgb[0]), int(target_rgb[1]), int(target_rgb[2]))
    r = 1 if tr > 0 else 0
    g = 1 if tg > 0 else 0
    b = 1 if tb > 0 else 0
    if (r, g, b) == (0, 0, 0):
        # Target is non-black but all channels are 0? Be defensive.
        return (1, 0, 0)
    return (r, g, b)


def scaled_color_map_nonzero(
    full_colors: Dict[Tuple[int, int], Tuple[int, int, int]],
    *,
    scale: float,
    brightness: int,
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Scale per-key colors without collapsing non-black keys to full black."""

    s = float(scale)
    out: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    for (row, col), (r0, g0, b0) in full_colors.items():
        r0, g0, b0 = int(r0), int(g0), int(b0)
        if (r0, g0, b0) == (0, 0, 0):
            out[(row, col)] = (0, 0, 0)
            continue

        r = max(0, min(255, int(r0 * s)))
        g = max(0, min(255, int(g0 * s)))
        b = max(0, min(255, int(b0 * s)))
        if (r, g, b) == (0, 0, 0) and s > 0 and int(brightness) > 0:
            # Keep at least a tiny visible hint of the original color.
            r = 1 if r0 > 0 else 0
            g = 1 if g0 > 0 else 0
            b = 1 if b0 > 0 else 0

        out[(row, col)] = (r, g, b)

    return out
