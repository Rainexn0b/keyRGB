from __future__ import annotations

import math
import random
import time
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
    load_per_key_colors_from_config,
    scaled_color_map,
)
from src.core.effects.transitions import avoid_full_black
from src.core.logging_utils import log_throttled

# Reactive typing effects live in a dedicated module to keep this file smaller.
from src.core.effects.reactive import (
    evdev_key_name_to_key_id as _evdev_key_name_to_key_id,
    run_reactive_fade,
    run_reactive_rainbow,
    run_reactive_ripple,
    run_reactive_snake,
)


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


Color = Tuple[int, int, int]
Key = Tuple[int, int]


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def _pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Uses an ~80% baseline so effects never feel "stuck".
    """

    try:
        s = int(getattr(engine, "speed", 4) or 0)
    except Exception:
        s = 4
    # NOTE: Users expect speed=10 to be *much* faster than speed=5. Use a
    # quadratic curve so the top end has more range.
    s = max(0, min(10, s))
    t = float(s) / 10.0
    t = t * t
    min_factor = float(min_factor)
    max_factor = float(max_factor)
    # Default pace range tuned for OpenRGB-style animations.
    if min_factor == 0.8 and max_factor == 2.2:
        min_factor = 0.25
        max_factor = 10.0
    return float(min_factor + (max_factor - min_factor) * t)


def _frame_dt_s() -> float:
    # Higher "resolution" comes from consistent high-FPS updates.
    return 1.0 / 60.0


def _has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(engine.kb, "set_key_colors", None))


def _base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    """Return the base key color map for effects.

    - If engine.per_key_colors is present, expand it across the keyboard.
    - Otherwise, use uniform color across all keys.
    """

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
    return {(r, c): tuple(map(int, rgb)) for (r, c), rgb in full.items()}


def _mix(a: Color, b: Color, t: float) -> Color:
    tt = _clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * tt)),
        int(round(a[1] + (b[1] - a[1]) * tt)),
        int(round(a[2] + (b[2] - a[2]) * tt)),
    )


def _scale(rgb: Color, s: float) -> Color:
    ss = _clamp01(s)
    return (int(round(rgb[0] * ss)), int(round(rgb[1] * ss)), int(round(rgb[2] * ss)))


def _render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    """Render per-key when available, otherwise fall back to uniform."""

    if _has_per_key(engine):
        try:
            enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_key_colors(color_map, brightness=int(engine.brightness), enable_user_mode=False)
            return
        except Exception as exc:
            # Do not crash the effect thread; fall back to uniform rendering.
            log_throttled(
                logger,
                "effects.render.per_key_failed",
                interval_s=30,
                level=logging.WARNING,
                msg="Per-key render failed; falling back to uniform",
                exc=exc,
            )

    # Uniform fallback: average the map to a single color.
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
        engine.kb.set_color((r, g, b), brightness=int(engine.brightness))


def run_breathing(engine: "EffectsEngine") -> None:
    """Breathing (SW): smooth breathing that respects per-key when available."""

    base = _base_color_map(engine)
    phase = 0.0
    dt = _frame_dt_s()
    pace = _pace(engine)

    while engine.running and not engine.stop_event.is_set():
        # Smoothstep'd sine for a natural breath.
        breath = (math.sin(phase) + 1.0) / 2.0
        breath = breath * breath * (3.0 - 2.0 * breath)
        breath = 0.12 + breath * 0.88

        color_map = {k: _scale(rgb, breath) for k, rgb in base.items()}
        _render(engine, color_map=color_map)

        phase += 0.08 * pace
        engine.stop_event.wait(dt)


def run_fire(engine: "EffectsEngine") -> None:
    """Fire (SW): higher-FPS, smoother flames; overlays onto per-key base when present."""

    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    heat: List[List[float]] = [[0.0 for _ in range(NUM_COLS)] for _ in range(NUM_ROWS)]

    def heat_to_rgb(h: float) -> Color:
        hh = _clamp01(h)
        # Simple gradient: dark red -> orange -> yellow.
        if hh < 0.5:
            t = hh / 0.5
            return (int(255 * t), int(80 * t), 0)
        t = (hh - 0.5) / 0.5
        return (255, int(80 + (175 * t)), int(0 + (20 * t)))

    while engine.running and not engine.stop_event.is_set():
        # Cool + rise diffusion.
        cooling = 0.06 * pace
        for r in range(NUM_ROWS):
            for c in range(NUM_COLS):
                heat[r][c] = max(0.0, heat[r][c] - cooling)

        # NOTE: The device row coordinate system maps row 0 to the bottom of
        # the deck (spacebar area) and row NUM_ROWS-1 to the top (F-keys).
        # Generate sparks near the bottom rows so the fire burns upward.
        sparks = max(1, int(2 * pace))
        for _ in range(sparks):
            c = random.randrange(NUM_COLS)
            r = random.randrange(min(2, NUM_ROWS))
            heat[r][c] = min(1.0, heat[r][c] + random.uniform(0.45, 0.9))

        # Diffuse upwards (toward larger row indices).
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
                # Overlay: keep some of the base color so per-key profiles still "read".
                color_map[(r, c)] = _mix(base_rgb, fire_rgb, t=min(1.0, h * 0.95))

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_random(engine: "EffectsEngine") -> None:
    """Random (SW): frequent, smooth cross-fades; per-key when available."""

    dt = _frame_dt_s()
    pace = _pace(engine)
    base = _base_color_map(engine)

    # Cross-fade state.
    prev = dict(base)
    target = dict(base)
    t = 1.0
    next_change_s = 0.0

    while engine.running and not engine.stop_event.is_set():
        now = time.monotonic()
        if now >= next_change_s:
            prev = dict(target)

            # New random targets; keep it bright enough to be visible.
            for k in target.keys():
                rr = random.randint(0, 255)
                gg = random.randint(0, 255)
                bb = random.randint(0, 255)
                if int(getattr(engine, "brightness", 25) or 0) > 0 and (rr, gg, bb) == (0, 0, 0):
                    rr = 1
                target[k] = (rr, gg, bb)

            t = 0.0
            # Faster changes at higher pace.
            next_change_s = now + (0.75 / pace)

        # Fade progression.
        t = min(1.0, t + dt * (1.8 * pace))
        color_map = {k: _mix(prev[k], target[k], t) for k in target.keys()}
        _render(engine, color_map=color_map)

        engine.stop_event.wait(dt)


def run_rainbow_wave(engine: "EffectsEngine") -> None:
    """Rainbow Wave (SW): classic OpenRGB-style rainbow wave across the keyboard.

    Clean-room implementation: a smoothly time-advancing hue gradient across the
    key matrix.
    """

    dt = _frame_dt_s()
    pace = _pace(engine)

    # Precompute normalized positions (stable across frames).
    col_den = float(max(1, NUM_COLS - 1))
    row_den = float(max(1, NUM_ROWS - 1))
    pos: Dict[Key, float] = {}
    for r in range(NUM_ROWS):
        for c in range(NUM_COLS):
            # Mostly horizontal wave with a slight diagonal bias.
            pos[(r, c)] = (float(c) / col_den) + (0.18 * (float(r) / row_den))

    hue = 0.0
    while engine.running and not engine.stop_event.is_set():
        # Advance hue at a comfortable rate; higher speed = faster movement.
        hue = (hue + (dt * (0.165 * pace))) % 1.0

        color_map: Dict[Key, Color] = {}
        for k, p in pos.items():
            h = (hue + p) % 1.0
            color_map[k] = hsv_to_rgb(h, 1.0, 1.0)

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_rainbow_swirl(engine: "EffectsEngine") -> None:
    """Rainbow Swirl (SW): OpenRGB-style swirl around the keyboard center."""

    dt = _frame_dt_s()
    pace = _pace(engine)

    # Stable per-key polar coordinates around the matrix center.
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
        hue = (hue + (dt * (0.115 * pace))) % 1.0

        color_map: Dict[Key, Color] = {}
        for k, (ang, rad) in coords.items():
            # Angle drives the swirl; distance adds mild spiral distortion.
            h = (hue + ang + 0.25 * (rad / max_r)) % 1.0
            color_map[k] = hsv_to_rgb(h, 1.0, 1.0)

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_spectrum_cycle(engine: "EffectsEngine") -> None:
    """Spectrum Cycle (SW): OpenRGB-style uniform hue cycling."""

    dt = _frame_dt_s()
    pace = _pace(engine)
    hue = 0.0

    while engine.running and not engine.stop_event.is_set():
        hue = (hue + (dt * (0.22 * pace))) % 1.0
        rgb = hsv_to_rgb(hue, 1.0, 1.0)
        color_map = {(r, c): rgb for r in range(NUM_ROWS) for c in range(NUM_COLS)}
        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_color_cycle(engine: "EffectsEngine") -> None:
    """Color Cycle (SW): smooth RGB cycling (OpenRGB-style)."""

    dt = _frame_dt_s()
    pace = _pace(engine)
    phase = 0.0

    while engine.running and not engine.stop_event.is_set():
        # Three phase-shifted sines for a smooth RGB cycle.
        r = (math.sin(phase) + 1.0) / 2.0
        g = (math.sin(phase + (2.0 * math.pi / 3.0)) + 1.0) / 2.0
        b = (math.sin(phase + (4.0 * math.pi / 3.0)) + 1.0) / 2.0
        rgb = (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
        color_map = {(rr, cc): rgb for rr in range(NUM_ROWS) for cc in range(NUM_COLS)}
        _render(engine, color_map=color_map)

        phase += dt * (1.8 * pace)
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

    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    twinkles: List[_Twinkle] = []
    acc = 0.0

    while engine.running and not engine.stop_event.is_set():
        # Spawn rate scales with pace.
        acc += dt * pace
        while acc >= 0.12:
            acc -= 0.12
            count = 1 if pace < 4.5 else 2
            for _ in range(count):
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)
                # Random vivid color.
                h = random.random()
                twinkles.append(
                    _Twinkle(
                        row=rr,
                        col=cc,
                        age_s=0.0,
                        ttl_s=max(0.10, 0.45 / pace),
                        color=hsv_to_rgb(h, 1.0, 1.0),
                    )
                )

        # Age and keep alive.
        alive: List[_Twinkle] = []
        for t in twinkles:
            t.age_s += dt
            if t.age_s <= t.ttl_s:
                alive.append(t)
        twinkles = alive

        overlay: Dict[Key, tuple[Color, float]] = {}
        for t in twinkles:
            # Ease-out intensity.
            x = 1.0 - (t.age_s / t.ttl_s)
            intensity = x * x
            k = (t.row, t.col)
            prev = overlay.get(k)
            if prev is None or intensity > prev[1]:
                overlay[k] = (t.color, intensity)

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            if k in overlay:
                c, w = overlay[k]
                color_map[k] = _mix(base_rgb, c, t=w)
            else:
                color_map[k] = base_rgb

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_strobe(engine: "EffectsEngine") -> None:
    """Strobe (SW): rapid on/off flashing (OpenRGB-style)."""

    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    # Faster at higher pace, with a sensible minimum.
    half_period_s = max(0.04, 0.38 / pace)
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

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_chase(engine: "EffectsEngine") -> None:
    """Chase (SW): moving highlight band across the keyboard (OpenRGB-style)."""

    per_key_ok = _has_per_key(engine)
    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    # Use the currently selected color as the chase highlight. In uniform fallback
    # mode, a literal moving band averages out to a constant color, so we also
    # add a gentle global pulse to keep it visibly animated.
    highlight_src = getattr(engine, "current_color", None) or (255, 0, 0)
    highlight = (int(highlight_src[0]), int(highlight_src[1]), int(highlight_src[2]))
    background = _scale(highlight, 0.06)

    pos = 0.0
    width = 1.6
    while engine.running and not engine.stop_event.is_set():
        pos = (pos + dt * (3.2 * pace)) % float(max(1, NUM_COLS))

        if not per_key_ok:
            # Uniform fallback: pulse between background and highlight.
            phase = float(pos) / float(max(1, NUM_COLS))
            pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2.0 * math.pi * phase))
            rgb = _mix(background, highlight, t=pulse)
            color_map = {(r, c): rgb for r in range(NUM_ROWS) for c in range(NUM_COLS)}
            _render(engine, color_map=color_map)
            engine.stop_event.wait(dt)
            continue

        color_map = {}
        for (r, c), base_rgb in base.items():
            # Distance on a wrapping ring.
            d = abs(float(c) - pos)
            d = min(d, float(NUM_COLS) - d)
            if d <= width:
                w = 1.0 - (d / max(1e-6, width))
                # Blend from background -> highlight for an obvious chase band.
                color_map[(r, c)] = _mix(background, highlight, t=w)
            else:
                color_map[(r, c)] = background

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)




def run_rain(engine: "EffectsEngine") -> None:
    """Rain: falling droplets with smooth fades; overlays onto per-key base when present."""

    @dataclass
    class _RainDrop:
        row: int
        col: int
        age_s: float
        ttl_s: float

    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    droplets: List[_RainDrop] = []

    def spawn() -> None:
        col = random.randrange(NUM_COLS)
        # Spawn at the top of the deck (F-keys).
        droplets.append(_RainDrop(row=NUM_ROWS - 1, col=col, age_s=0.0, ttl_s=1.1 / pace))

    # Spawn cadence
    acc = 0.0
    while engine.running and not engine.stop_event.is_set():
        acc += dt * pace
        if acc >= 0.18:
            acc = 0.0
            spawn()

        # Update droplets and build overlay.
        new_droplets: List[_RainDrop] = []
        overlay: Dict[Key, float] = {}
        for d in droplets:
            d.age_s += dt
            if d.age_s > d.ttl_s:
                continue

            # Droplet falls from top (F-keys) to bottom (spacebar area) over its TTL.
            progress = d.age_s / d.ttl_s
            row_f = (1.0 - progress) * float(NUM_ROWS - 1)
            row = int(round(row_f))
            if 0 <= row < NUM_ROWS:
                # Small tail.
                for tail in range(0, 3):
                    # Tail trails behind upwards (toward the top of the deck).
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
            color_map[k] = _mix(base_rgb, rain_rgb, t=min(1.0, w))

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)
