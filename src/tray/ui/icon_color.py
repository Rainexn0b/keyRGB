from __future__ import annotations

import colorsys
import math
import time
from collections.abc import Iterable, Mapping
from typing import Any

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid


def _pace_from_speed(speed: int) -> float:
    # Mirror src.core.effects.software.base.pace(engine) mapping.
    s = max(0, min(10, int(speed)))
    t = float(s) / 10.0
    t = t * t
    return float(0.25 + (10.0 - 0.25) * t)


def _per_key_color_mapping(config: Any) -> Mapping[tuple[int, int], tuple[int, int, int]]:
    try:
        per_key = getattr(config, "per_key_colors", {}) or {}
    except Exception:
        return {}
    return per_key if isinstance(per_key, Mapping) else {}


def _weighted_hsv_mean(colors: Iterable[tuple[int, int, int]]) -> tuple[int, int, int]:
    # Avoid muddy greys when averaging multi-color maps by averaging hue on the
    # unit circle and weighting by saturation/value.
    total = 0.0
    x = 0.0
    y = 0.0
    s_acc = 0.0
    v_acc = 0.0
    count = 0
    r_sum = 0
    g_sum = 0
    b_sum = 0

    for r, g, b in colors:
        count += 1
        r_sum += int(r)
        g_sum += int(g)
        b_sum += int(b)
        rr = max(0, min(255, int(r))) / 255.0
        gg = max(0, min(255, int(g))) / 255.0
        bb = max(0, min(255, int(b))) / 255.0
        h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)
        if v <= 0.0:
            continue
        w = max(1e-6, s * v)
        ang = 2.0 * math.pi * h
        x += math.cos(ang) * w
        y += math.sin(ang) * w
        s_acc += s * w
        v_acc += v * w
        total += w

    if total <= 1e-6 or (x == 0.0 and y == 0.0):
        if count == 0:
            return (255, 0, 128)
        r = int(round(r_sum / count))
        g = int(round(g_sum / count))
        b = int(round(b_sum / count))
        return (r, g, b)

    mean_h = (math.atan2(y, x) / (2.0 * math.pi)) % 1.0
    mean_s = max(0.0, min(1.0, s_acc / total))
    mean_v = max(0.0, min(1.0, v_acc / total))
    rr, gg, bb = colorsys.hsv_to_rgb(mean_h, mean_s, mean_v)
    return (int(rr * 255), int(gg * 255), int(bb * 255))


def _representative_perkey_color(config: Any) -> tuple[int, int, int] | None:
    per_key = _per_key_color_mapping(config)
    if not per_key:
        return None

    base_color = tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))
    try:
        full = build_full_color_grid(
            base_color=base_color,
            per_key_colors=per_key,
            num_rows=NUM_ROWS,
            num_cols=NUM_COLS,
        )
        return _weighted_hsv_mean(full.values())
    except Exception:
        return _weighted_hsv_mean(per_key.values())


def _representative_saved_perkey_color(config: Any) -> tuple[int, int, int] | None:
    per_key = _per_key_color_mapping(config)
    return _weighted_hsv_mean(per_key.values()) if per_key else None


def representative_color(
    *,
    config: Any,
    is_off: bool,
    now: float | None = None,
) -> tuple[int, int, int]:
    """Pick an RGB color representative of the currently applied state."""

    if now is None:
        now = time.time()

    # Off state
    if is_off or getattr(config, "brightness", 0) == 0:
        return (64, 64, 64)

    effect = str(getattr(config, "effect", "none") or "none")
    brightness = int(getattr(config, "brightness", 25) or 25)

    # Reactive typing effects can store a separate manual effect color.
    # Respect the "use manual color" toggle; when disabled, the icon should
    # mirror the configured base color rather than a stale stored reactive
    # color override.
    is_reactive = effect.startswith("reactive_")
    # NOTE: For the tray icon we intentionally follow the profile/policy
    # brightness (config.brightness). Reactive pulse intensity is tracked
    # separately via config.reactive_brightness.

    # Per-key: average of configured colors
    if effect == "perkey":
        try:
            brightness = int(getattr(config, "perkey_brightness", brightness) or brightness)
        except Exception:
            pass
        base = _representative_perkey_color(config) or tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))

    # Multi-color effects: cycle a hue so the icon changes.
    elif effect in {"rainbow_wave", "rainbow_swirl", "spectrum_cycle", "color_cycle"}:
        speed = int(getattr(config, "speed", 5) or 5)
        p = _pace_from_speed(speed)

        if effect == "rainbow_wave":
            hue = (now * (0.165 * p)) % 1.0
            col_den = float(max(1, NUM_COLS - 1))
            row_den = float(max(1, NUM_ROWS - 1))
            r = NUM_ROWS // 2
            c = NUM_COLS // 2
            position = (float(c) / col_den) + (0.18 * (float(r) / row_den))
            h = (hue + position) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

        elif effect == "rainbow_swirl":
            hue = (now * (0.115 * p)) % 1.0
            cr = (NUM_ROWS - 1) / 2.0
            cc = (NUM_COLS - 1) / 2.0
            r = NUM_ROWS // 2
            c = NUM_COLS // 2
            dy = float(r) - cr
            dx = float(c) - cc
            ang = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
            rad = math.hypot(dx, dy)
            max_r = math.hypot(max(cc, NUM_COLS - 1 - cc), max(cr, NUM_ROWS - 1 - cr))
            max_r = max(1e-6, max_r)
            h = (hue + ang + 0.25 * (rad / max_r)) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(h, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

        elif effect == "color_cycle":
            phase = now * (1.8 * p)
            r = (math.sin(phase) + 1.0) / 2.0
            g = (math.sin(phase + (2.0 * math.pi / 3.0)) + 1.0) / 2.0
            b = (math.sin(phase + (4.0 * math.pi / 3.0)) + 1.0) / 2.0
            base = (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

        else:  # spectrum_cycle
            hue = (now * (0.22 * p)) % 1.0
            rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            base = (int(rr * 255), int(gg * 255), int(bb * 255))

    elif effect in {"rainbow", "random", "aurora", "fireworks", "wave", "marquee"}:
        # Hardware and mixed effects: keep a cheap animated approximation.
        speed = int(getattr(config, "speed", 5) or 5)
        p = _pace_from_speed(speed)
        hue = (now * (0.18 * p)) % 1.0
        rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        base = (int(rr * 255), int(gg * 255), int(bb * 255))

    else:
        if is_reactive:
            use_manual_reactive_color = bool(getattr(config, "reactive_use_manual_color", False))
            if use_manual_reactive_color:
                base = tuple(getattr(config, "reactive_color", None) or getattr(config, "color", None) or (255, 0, 128))
            else:
                try:
                    brightness = int(getattr(config, "perkey_brightness", brightness) or brightness)
                except Exception:
                    pass
                base = _representative_saved_perkey_color(config) or tuple(getattr(config, "color", None) or (255, 0, 128))
            try:
                if tuple(base) == (0, 0, 0):
                    base = (255, 0, 128)
            except Exception:
                base = (255, 0, 128)
        else:
            base = tuple(getattr(config, "color", (255, 0, 128)) or (255, 0, 128))

    # Scale by brightness (0..50), but bias brighter than the keyboard so the
    # tray icon stays readable in dark mode at low keyboard brightness.
    #
    # Ratio: approximately 1:3 (keyboard:icon), clamped to [0.25, 1.0].
    icon_brightness = max(0, min(50, int(round(float(brightness) * 3.0))))
    scale = max(0.25, min(1.0, icon_brightness / 50.0))
    return (
        int(max(0, min(255, base[0] * scale))),
        int(max(0, min(255, base[1] * scale))),
        int(max(0, min(255, base[2] * scale))),
    )
