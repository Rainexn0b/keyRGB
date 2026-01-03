from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS

from .base import (
    Color,
    Key,
    base_color_map,
    clamp01,
    frame_dt_s,
    has_per_key,
    mix,
    pace,
    render,
    scale,
)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def run_breathing(engine: "EffectsEngine") -> None:
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
        render(engine, color_map=color_map)

        phase += 0.08 * p
        engine.stop_event.wait(dt)


def run_fire(engine: "EffectsEngine") -> None:
    """Fire (SW): higher-FPS, smoother flames; overlays onto per-key base when present."""

    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    heat: List[List[float]] = [[0.0 for _ in range(NUM_COLS)] for _ in range(NUM_ROWS)]

    def heat_to_rgb(h: float) -> Color:
        hh = clamp01(h)
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

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_random(engine: "EffectsEngine") -> None:
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
        render(engine, color_map=color_map)

        engine.stop_event.wait(dt)


def run_rainbow_wave(engine: "EffectsEngine") -> None:
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

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_rainbow_swirl(engine: "EffectsEngine") -> None:
    """Rainbow Swirl (SW): OpenRGB-style swirl around the keyboard center."""

    dt = frame_dt_s()
    p = pace(engine)

    cr = (NUM_ROWS - 1) / 2.0
    cc = (NUM_COLS - 1) / 2.0
    coords: Dict[Key, Tuple[float, float]] = {}
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

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_spectrum_cycle(engine: "EffectsEngine") -> None:
    """Spectrum Cycle (SW): OpenRGB-style uniform hue cycling."""

    dt = frame_dt_s()
    p = pace(engine)
    hue = 0.0

    while engine.running and not engine.stop_event.is_set():
        hue = (hue + (dt * (0.22 * p))) % 1.0
        rgb = hsv_to_rgb(hue, 1.0, 1.0)
        color_map = {(r, c): rgb for r in range(NUM_ROWS) for c in range(NUM_COLS)}
        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_color_cycle(engine: "EffectsEngine") -> None:
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
        render(engine, color_map=color_map)

        phase += dt * (1.8 * p)
        engine.stop_event.wait(dt)


@dataclass
class _Twinkle:
    row: int
    col: int
    age_s: float
    ttl_s: float
    color: Color


def run_twinkle(engine: "EffectsEngine") -> None:
    """Twinkle (SW): random sparkles that fade out (OpenRGB-style)."""

    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    twinkles: List[_Twinkle] = []
    acc = 0.0

    while engine.running and not engine.stop_event.is_set():
        acc += dt * p
        while acc >= 0.12:
            acc -= 0.12
            count = 1 if p < 4.5 else 2
            for _ in range(count):
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)
                h = random.random()
                twinkles.append(
                    _Twinkle(
                        row=rr,
                        col=cc,
                        age_s=0.0,
                        ttl_s=max(0.10, 0.45 / p),
                        color=hsv_to_rgb(h, 1.0, 1.0),
                    )
                )

        alive: List[_Twinkle] = []
        for tw in twinkles:
            tw.age_s += dt
            if tw.age_s <= tw.ttl_s:
                alive.append(tw)
        twinkles = alive

        overlay: Dict[Key, Tuple[Color, float]] = {}
        for tw in twinkles:
            x = 1.0 - (tw.age_s / tw.ttl_s)
            intensity = x * x
            k = (tw.row, tw.col)
            prev = overlay.get(k)
            if prev is None or intensity > prev[1]:
                overlay[k] = (tw.color, intensity)

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            if k in overlay:
                c, w = overlay[k]
                color_map[k] = mix(base_rgb, c, t=w)
            else:
                color_map[k] = base_rgb

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_strobe(engine: "EffectsEngine") -> None:
    """Strobe (SW): rapid on/off flashing (OpenRGB-style)."""

    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    half_period_s = max(0.04, 0.38 / p)
    elapsed = 0.0
    on = False

    while engine.running and not engine.stop_event.is_set():
        elapsed += dt
        if elapsed >= half_period_s:
            elapsed = 0.0
            on = not on

        if on:
            color_map = dict(base)
        else:
            color_map = {k: (0, 0, 0) for k in base.keys()}

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_chase(engine: "EffectsEngine") -> None:
    """Chase (SW): moving highlight band across the keyboard (OpenRGB-style)."""

    per_key_ok = has_per_key(engine)
    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    highlight_src = getattr(engine, "current_color", None) or (255, 0, 0)
    highlight = (int(highlight_src[0]), int(highlight_src[1]), int(highlight_src[2]))
    background = scale(highlight, 0.06)

    pos = 0.0
    width = 1.6
    while engine.running and not engine.stop_event.is_set():
        pos = (pos + dt * (3.2 * p)) % float(max(1, NUM_COLS))

        if not per_key_ok:
            phase = float(pos) / float(max(1, NUM_COLS))
            pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2.0 * math.pi * phase))
            rgb = mix(background, highlight, t=pulse)
            color_map = {(r, c): rgb for r in range(NUM_ROWS) for c in range(NUM_COLS)}
            render(engine, color_map=color_map)
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for (r, c), _base_rgb in base.items():
            d = abs(float(c) - pos)
            d = min(d, float(NUM_COLS) - d)
            if d <= width:
                w = 1.0 - (d / max(1e-6, width))
                color_map[(r, c)] = mix(background, highlight, t=w)
            else:
                color_map[(r, c)] = background

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_rain(engine: "EffectsEngine") -> None:
    """Rain: falling droplets with smooth fades; overlays onto per-key base when present."""

    @dataclass
    class _RainDrop:
        row: int
        col: int
        age_s: float
        ttl_s: float

    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    droplets: List[_RainDrop] = []

    def spawn() -> None:
        col = random.randrange(NUM_COLS)
        droplets.append(_RainDrop(row=NUM_ROWS - 1, col=col, age_s=0.0, ttl_s=1.1 / p))

    acc = 0.0
    while engine.running and not engine.stop_event.is_set():
        acc += dt * p
        if acc >= 0.18:
            acc = 0.0
            spawn()

        new_droplets: List[_RainDrop] = []
        overlay: Dict[Key, float] = {}
        for d in droplets:
            d.age_s += dt
            if d.age_s > d.ttl_s:
                continue

            progress = d.age_s / d.ttl_s
            row_f = (1.0 - progress) * float(NUM_ROWS - 1)
            row = int(round(row_f))
            if 0 <= row < NUM_ROWS:
                for tail in range(0, 3):
                    rr = row + tail
                    if rr >= NUM_ROWS:
                        break
                    w = max(0.0, 1.0 - (tail * 0.35)) * (1.0 - progress)
                    k = (rr, d.col)
                    overlay[k] = max(overlay.get(k, 0.0), w)
            new_droplets.append(d)

        droplets = new_droplets

        rain_rgb = (40, 140, 255)
        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            color_map[k] = mix(base_rgb, rain_rgb, t=min(1.0, w))

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)
