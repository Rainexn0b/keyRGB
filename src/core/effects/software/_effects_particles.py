from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.transitions import scaled_color_map_nonzero

from ._buffers import fill_uniform_color_map, get_engine_color_map_buffer
from .base import (
    animation_step_s,
    Color,
    Key,
    base_color_map,
    frame_dt_s,
    has_per_key,
    mix,
    pace,
    render as base_render,
    scale,
)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


@dataclass
class _Twinkle:
    row: int
    col: int
    age_s: float
    ttl_s: float
    color: Color


def run_twinkle(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Twinkle (SW): random sparkles that fade out (OpenRGB-style)."""

    base = base_color_map(engine)
    nominal_dt = frame_dt_s()
    p = pace(engine)
    color_map = get_engine_color_map_buffer(engine, "_sw_twinkle_frame_map")

    twinkles: List[_Twinkle] = []
    acc = 0.0

    while engine.running and not engine.stop_event.is_set():
        step_s = animation_step_s(engine, "_sw_twinkle_tick", nominal_s=nominal_dt)
        acc += step_s * p
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
            tw.age_s += step_s
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

        color_map.clear()
        for k, base_rgb in base.items():
            if k in overlay:
                c, w = overlay[k]
                color_map[k] = mix(base_rgb, c, t=w)
            else:
                color_map[k] = base_rgb

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(nominal_dt)


def run_strobe(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Strobe (SW): rapid on/off flashing (OpenRGB-style)."""

    base = base_color_map(engine)
    try:
        brightness_raw = getattr(engine, "brightness", 25)
        brightness = int(brightness_raw or 0)
    except (TypeError, ValueError):
        brightness = 0

    # If the base is fully black but brightness is non-zero, the effect would
    # otherwise appear "stuck off". Fall back to a visible base.
    if brightness > 0 and not any(rgb != (0, 0, 0) for rgb in base.values()):
        base = {(r, c): (255, 255, 255) for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    # Avoid writing a full-black frame: some devices/backends interpret
    # (0,0,0) as an "off" latch and won't recover smoothly. Instead, render a
    # dimmed version of the base.
    off_map = scaled_color_map_nonzero(base, scale=0.08, brightness=brightness)
    nominal_dt = frame_dt_s()
    p = pace(engine)

    half_period_s = max(0.04, 0.38 / p)
    elapsed = 0.0
    # Start "on" so selecting the effect doesn't immediately blank the keyboard.
    on = True
    color_map = get_engine_color_map_buffer(engine, "_sw_strobe_frame_map")

    while engine.running and not engine.stop_event.is_set():
        step_s = animation_step_s(engine, "_sw_strobe_tick", nominal_s=nominal_dt)
        elapsed += step_s
        if elapsed >= half_period_s:
            elapsed = 0.0
            on = not on

        color_map.clear()
        color_map.update(base if on else off_map)

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(nominal_dt)


def run_chase(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Chase (SW): moving highlight band across the keyboard (OpenRGB-style)."""

    per_key_ok = has_per_key(engine)
    base = base_color_map(engine)
    nominal_dt = frame_dt_s()
    p = pace(engine)

    highlight_src = getattr(engine, "current_color", None)
    if highlight_src is None:
        highlight_src = (255, 0, 0)
    highlight = (int(highlight_src[0]), int(highlight_src[1]), int(highlight_src[2]))
    if highlight == (0, 0, 0):
        # When the current uniform color is black (common in per-key mode),
        # still provide a visible chase highlight.
        highlight = (255, 0, 0)

    # Use the per-key base as the background when available; otherwise use
    # a dim version of the highlight.
    background_uniform = scale(highlight, 0.06)

    pos = 0.0
    width = 1.6
    color_map = get_engine_color_map_buffer(engine, "_sw_chase_frame_map")
    while engine.running and not engine.stop_event.is_set():
        step_s = animation_step_s(engine, "_sw_chase_tick", nominal_s=nominal_dt)
        pos = (pos + step_s * (3.2 * p)) % float(max(1, NUM_COLS))

        if not per_key_ok:
            phase = float(pos) / float(max(1, NUM_COLS))
            pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2.0 * math.pi * phase))
            rgb = mix(background_uniform, highlight, t=pulse)
            fill_uniform_color_map(color_map, color=rgb)
            render_fn(engine, color_map=color_map)
            engine.stop_event.wait(nominal_dt)
            continue

        color_map.clear()
        for (r, c), base_rgb in base.items():
            d = abs(float(c) - pos)
            d = min(d, float(NUM_COLS) - d)
            if d <= width:
                w = 1.0 - (d / max(1e-6, width))
                color_map[(r, c)] = mix(base_rgb, highlight, t=w)
            else:
                color_map[(r, c)] = base_rgb

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(nominal_dt)


def run_rain(engine: "EffectsEngine", *, render_fn=base_render) -> None:
    """Rain: falling droplets with smooth fades; overlays onto per-key base when present."""

    @dataclass
    class _RainDrop:
        row: int
        col: int
        age_s: float
        ttl_s: float

    base = base_color_map(engine)
    nominal_dt = frame_dt_s()
    p = pace(engine)
    color_map = get_engine_color_map_buffer(engine, "_sw_rain_frame_map")

    droplets: List[_RainDrop] = []

    def spawn() -> None:
        col = random.randrange(NUM_COLS)
        droplets.append(_RainDrop(row=NUM_ROWS - 1, col=col, age_s=0.0, ttl_s=1.1 / p))

    acc = 0.0
    while engine.running and not engine.stop_event.is_set():
        step_s = animation_step_s(engine, "_sw_rain_tick", nominal_s=nominal_dt)
        acc += step_s * p
        if acc >= 0.18:
            acc = 0.0
            spawn()

        new_droplets: List[_RainDrop] = []
        overlay: Dict[Key, float] = {}
        for d in droplets:
            d.age_s += step_s
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
        color_map.clear()
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            color_map[k] = mix(base_rgb, rain_rgb, t=min(1.0, w))

        render_fn(engine, color_map=color_map)
        engine.stop_event.wait(nominal_dt)
