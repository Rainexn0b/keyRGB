from __future__ import annotations

import math
import random
import time
from typing import TYPE_CHECKING, Dict

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS

from .base import Color, Key, base_color_map, frame_dt_s, mix, pace, render as base_render, scale

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def run_breathing(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Breathing (SW): smooth breathing that respects per-key when available."""

    base = base_color_map(engine)
    phase = 0.0
    dt = frame_dt_s()
    p = pace(engine)

    while engine.running and not engine.stop_event.is_set():
        breath = (math.sin(phase) + 1.0) / 2.0
        breath = breath * breath * (3.0 - 2.0 * breath)
        breath = 0.12 + breath * 0.88

        color_map = {k: scale(rgb, breath) for k, rgb in base.items()}
        render_fn(engine, color_map=color_map)

        phase += 0.08 * p
        engine.stop_event.wait(dt)


def run_fire(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Fire (SW): higher-FPS, smoother flames; overlays onto per-key base when present."""

    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    heat = [[0.0 for _ in range(NUM_COLS)] for _ in range(NUM_ROWS)]

    def heat_to_rgb(h: float) -> Color:
        hh = max(0.0, min(1.0, float(h)))
        if hh < 0.5:
            t = hh / 0.5
            return (int(255 * t), int(80 * t), 0)
        t = (hh - 0.5) / 0.5
        return (255, int(80 + (175 * t)), int(0 + (20 * t)))

    while engine.running and not engine.stop_event.is_set():
        cooling = 0.06 * p
        for r in range(NUM_ROWS):
            for c in range(NUM_COLS):
                heat[r][c] = max(0.0, heat[r][c] - cooling)

        sparks = max(1, int(2 * p))
        for _ in range(sparks):
            c = random.randrange(NUM_COLS)
            r = random.randrange(min(2, NUM_ROWS))
            heat[r][c] = min(1.0, heat[r][c] + random.uniform(0.45, 0.9))

        for r in range(1, NUM_ROWS):
            for c in range(NUM_COLS):
                below = heat[r - 1][c]
                below_l = heat[r - 1][c - 1] if c > 0 else below
                below_r = heat[r - 1][c + 1] if c + 1 < NUM_COLS else below
                heat[r][c] = (below + below_l + below_r) / 3.0

        color_map: Dict[Key, Color] = {}
        for r in range(NUM_ROWS):
            for c in range(NUM_COLS):
                h = heat[r][c]
                fire_rgb = heat_to_rgb(h)
                base_rgb = base[(r, c)]
                color_map[(r, c)] = mix(base_rgb, fire_rgb, t=min(1.0, h * 0.95))

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_random(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Random (SW): frequent, smooth cross-fades; per-key when available."""

    dt = frame_dt_s()
    p = pace(engine)
    base = base_color_map(engine)

    prev = dict(base)
    target = dict(base)
    t = 1.0
    next_change_s = 0.0

    while engine.running and not engine.stop_event.is_set():
        now = time.monotonic()
        if now >= next_change_s:
            prev = dict(target)

            for k in target.keys():
                rr = random.randint(0, 255)
                gg = random.randint(0, 255)
                bb = random.randint(0, 255)
                if int(getattr(engine, "brightness", 25) or 0) > 0 and (rr, gg, bb) == (0, 0, 0):
                    rr = 1
                target[k] = (rr, gg, bb)

            t = 0.0
            next_change_s = now + (0.75 / p)

        t = min(1.0, t + dt * (1.8 * p))
        color_map = {k: mix(prev[k], target[k], t) for k in target.keys()}
        render_fn(engine, color_map=color_map)

        engine.stop_event.wait(dt)


def run_rainbow_wave(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Rainbow Wave (SW): OpenRGB-style hue gradient wave across the key matrix."""

    dt = frame_dt_s()
    p = pace(engine)

    col_den = float(max(1, NUM_COLS - 1))
    row_den = float(max(1, NUM_ROWS - 1))
    pos: Dict[Key, float] = {}
    for r in range(NUM_ROWS):
        for c in range(NUM_COLS):
            pos[(r, c)] = (float(c) / col_den) + (0.18 * (float(r) / row_den))

    hue = 0.0
    while engine.running and not engine.stop_event.is_set():
        hue = (hue + (dt * (0.165 * p))) % 1.0

        color_map: Dict[Key, Color] = {}
        for k, position in pos.items():
            h = (hue + position) % 1.0
            color_map[k] = hsv_to_rgb(h, 1.0, 1.0)

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_rainbow_swirl(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Rainbow Swirl (SW): OpenRGB-style swirl around the keyboard center."""

    dt = frame_dt_s()
    p = pace(engine)

    cr = (NUM_ROWS - 1) / 2.0
    cc = (NUM_COLS - 1) / 2.0
    coords: Dict[Key, tuple[float, float]] = {}
    max_r = 0.0
    for r in range(NUM_ROWS):
        for c in range(NUM_COLS):
            dy = float(r) - cr
            dx = float(c) - cc
            ang = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
            rad = math.hypot(dx, dy)
            coords[(r, c)] = (ang, rad)
            max_r = max(max_r, rad)

    max_r = max(1e-6, max_r)
    hue = 0.0
    while engine.running and not engine.stop_event.is_set():
        hue = (hue + (dt * (0.115 * p))) % 1.0

        color_map: Dict[Key, Color] = {}
        for k, (ang, rad) in coords.items():
            h = (hue + ang + 0.25 * (rad / max_r)) % 1.0
            color_map[k] = hsv_to_rgb(h, 1.0, 1.0)

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_spectrum_cycle(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Spectrum Cycle (SW): OpenRGB-style uniform hue cycling."""

    dt = frame_dt_s()
    p = pace(engine)
    hue = 0.0

    while engine.running and not engine.stop_event.is_set():
        hue = (hue + (dt * (0.22 * p))) % 1.0
        rgb = hsv_to_rgb(hue, 1.0, 1.0)
        color_map = {(r, c): rgb for r in range(NUM_ROWS) for c in range(NUM_COLS)}
        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_color_cycle(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Color Cycle (SW): smooth RGB cycling (OpenRGB-style)."""

    dt = frame_dt_s()
    p = pace(engine)
    phase = 0.0

    while engine.running and not engine.stop_event.is_set():
        r = (math.sin(phase) + 1.0) / 2.0
        g = (math.sin(phase + (2.0 * math.pi / 3.0)) + 1.0) / 2.0
        b = (math.sin(phase + (4.0 * math.pi / 3.0)) + 1.0) / 2.0
        rgb = (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
        color_map = {(rr, cc): rgb for rr in range(NUM_ROWS) for cc in range(NUM_COLS)}
        render_fn(engine, color_map=color_map)

        phase += dt * (1.8 * p)
        engine.stop_event.wait(dt)
