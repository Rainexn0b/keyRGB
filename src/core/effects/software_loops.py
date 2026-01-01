from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import (
    build_full_color_grid,
    enable_user_mode_once,
    load_per_key_colors_from_config,
    scaled_color_map,
)
from src.core.effects.transitions import avoid_full_black, choose_steps

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def run_pulse(engine: "EffectsEngine") -> None:
    """Pulse: rhythmic brightness pulses with the current color."""

    phase = 0.0
    interval = engine._clamped_interval(180, min_s=0.03)

    while engine.running and not engine.stop_event.is_set():
        pulse = (math.sin(phase) + 1) / 2  # 0-1
        pulse_brightness = int(round(engine.brightness * pulse))
        pulse_brightness = max(1, min(engine.brightness, pulse_brightness))

        with engine.kb_lock:
            engine.kb.set_color(engine.current_color, brightness=pulse_brightness)

        phase += 0.055
        engine.stop_event.wait(interval)


def run_strobe(engine: "EffectsEngine") -> None:
    """Strobe: rapid on/off flashing."""

    on = False
    interval = engine._clamped_interval(90, min_s=0.06)

    while engine.running and not engine.stop_event.is_set():
        with engine.kb_lock:
            if on:
                engine.kb.set_color((255, 255, 255), brightness=engine.brightness)
            else:
                engine.kb.set_color((0, 0, 0), brightness=max(1, engine.brightness))

        on = not on
        engine.stop_event.wait(interval)


def run_fire(engine: "EffectsEngine") -> None:
    """Fire: flickering red/orange flames."""

    interval = engine._clamped_interval(140, min_s=0.06)

    prev = None
    while engine.running and not engine.stop_event.is_set():
        factor = engine._brightness_factor()
        target = (
            int((200 + random.random() * 55) * factor),
            int((random.random() * 100) * factor),
            0,
        )

        if prev is None:
            prev = target

        steps = choose_steps(duration_s=float(interval), max_steps=10, target_fps=40.0, min_dt_s=0.02)
        dt = float(interval) / float(steps)
        pr, pg, pb = prev
        tr, tg, tb = target
        for i in range(1, steps + 1):
            if not engine.running or engine.stop_event.is_set():
                break
            t = float(i) / float(steps)
            r = int(round(pr + (tr - pr) * t))
            g = int(round(pg + (tg - pg) * t))
            b = int(round(pb + (tb - pb) * t))
            with engine.kb_lock:
                engine.kb.set_color((r, g, b), brightness=engine.brightness)
            engine.stop_event.wait(dt)

        prev = target


def run_random(engine: "EffectsEngine") -> None:
    """Random: random color changes with a smooth cross-fade."""

    interval = engine._clamped_interval(500, min_s=0.12)

    prev = None
    while engine.running and not engine.stop_event.is_set():
        factor = engine._brightness_factor()
        target = (
            int(random.random() * 255 * factor),
            int(random.random() * 255 * factor),
            int(random.random() * 255 * factor),
        )

        if int(engine.brightness) > 0 and tuple(target) == (0, 0, 0):
            target = (1, 0, 0)

        if prev is None:
            prev = target

        steps = choose_steps(duration_s=float(interval), max_steps=18, target_fps=45.0, min_dt_s=0.02)
        dt = float(interval) / float(steps)
        pr, pg, pb = prev
        tr, tg, tb = target
        for i in range(1, steps + 1):
            if not engine.running or engine.stop_event.is_set():
                break
            t = float(i) / float(steps)
            r = int(round(pr + (tr - pr) * t))
            g = int(round(pg + (tg - pg) * t))
            b = int(round(pb + (tb - pb) * t))

            r, g, b = avoid_full_black(
                rgb=(r, g, b),
                target_rgb=(tr, tg, tb),
                brightness=int(engine.brightness),
            )
            with engine.kb_lock:
                engine.kb.set_color((r, g, b), brightness=engine.brightness)
            engine.stop_event.wait(dt)

        prev = target


def run_perkey_breathing(engine: "EffectsEngine") -> None:
    """Per-key breathing: breathing animation that preserves each key's individual color."""

    phase = 0.0
    interval = engine._clamped_interval(90, min_s=0.04)

    if not engine.per_key_colors:
        engine.per_key_colors = load_per_key_colors_from_config()

    if not engine.per_key_colors:
        run_pulse(engine)
        return

    base_color_src = engine.current_color or (255, 0, 0)
    base_color = (int(base_color_src[0]), int(base_color_src[1]), int(base_color_src[2]))

    full_colors = build_full_color_grid(
        base_color=base_color,
        per_key_colors=engine.per_key_colors,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )

    enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=engine.brightness)

    while engine.running and not engine.stop_event.is_set():
        breath = (math.sin(phase) + 1.0) / 2.0
        breath = breath * breath * (3.0 - 2.0 * breath)  # smoothstep
        breath = 0.15 + breath * 0.85

        color_map = scaled_color_map(full_colors, scale=breath)

        with engine.kb_lock:
            engine.kb.set_key_colors(color_map, brightness=int(engine.brightness), enable_user_mode=False)

        phase += 0.08
        engine.stop_event.wait(interval)


def run_perkey_pulse(engine: "EffectsEngine") -> None:
    """Per-key pulse: pulse animation that preserves each key's individual color."""

    phase = 0.0
    interval = engine._clamped_interval(70, min_s=0.03)

    if not engine.per_key_colors:
        engine.per_key_colors = load_per_key_colors_from_config()

    if not engine.per_key_colors:
        run_pulse(engine)
        return

    base_color_src = engine.current_color or (255, 0, 0)
    base_color = (int(base_color_src[0]), int(base_color_src[1]), int(base_color_src[2]))

    full_colors = build_full_color_grid(
        base_color=base_color,
        per_key_colors=engine.per_key_colors,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )

    enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=engine.brightness)

    while engine.running and not engine.stop_event.is_set():
        pulse = (math.sin(phase) + 1.0) / 2.0
        pulse = pulse**3
        pulse = 0.08 + pulse * 0.92

        color_map = scaled_color_map(full_colors, scale=pulse)

        with engine.kb_lock:
            engine.kb.set_key_colors(color_map, brightness=int(engine.brightness), enable_user_mode=False)

        phase += 0.15
        engine.stop_event.wait(interval)
