from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.transitions import avoid_full_black

from .input import load_active_profile_keymap, poll_keypress_key_id, try_open_evdev_keyboards
from .render import Color, Key, base_color_map, frame_dt_s, has_per_key, mix, pace, render, scale

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


@dataclass
class _Pulse:
    row: int
    col: int
    age_s: float
    ttl_s: float


def _reactive_loop(engine: "EffectsEngine", *, mode: str) -> None:
    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    react_color_src = getattr(engine, "current_color", None) or (255, 255, 255)
    react_color = (int(react_color_src[0]), int(react_color_src[1]), int(react_color_src[2]))

    if not (getattr(engine, "per_key_colors", None) or None):
        background = scale(react_color, 0.06)
        base = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    devices = try_open_evdev_keyboards()
    synthetic = not devices
    spawn_acc = 0.0
    spawn_interval_s = max(0.10, 0.45 / max(0.1, p))

    keymap = load_active_profile_keymap()

    pulses: List[_Pulse] = []
    while engine.running and not engine.stop_event.is_set():
        pressed_key_id = poll_keypress_key_id(devices)
        pressed = bool(pressed_key_id)

        if synthetic:
            spawn_acc += dt
            if spawn_acc >= spawn_interval_s:
                spawn_acc = 0.0
                pressed = True

        if pressed:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            ttl = 0.40 / p
            pulses.append(_Pulse(row=rr, col=cc, age_s=0.0, ttl_s=ttl))

        new_pulses: List[_Pulse] = []
        for pulse in pulses:
            pulse.age_s += dt
            if pulse.age_s <= pulse.ttl_s:
                new_pulses.append(pulse)
        pulses = new_pulses

        overlay: Dict[Key, float] = {}
        for pulse in pulses:
            if mode == "fade":
                intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
                overlay[(pulse.row, pulse.col)] = max(overlay.get((pulse.row, pulse.col), 0.0), intensity)
                continue

            intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
            radius = int(round(1 + 5 * (pulse.age_s / pulse.ttl_s)))
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    r = pulse.row + dr
                    c = pulse.col + dc
                    if r < 0 or r >= NUM_ROWS or c < 0 or c >= NUM_COLS:
                        continue
                    d = abs(dr) + abs(dc)
                    if d > radius:
                        continue
                    w = max(0.0, intensity * (1.0 - (d / max(1.0, float(radius)))))
                    k = (r, c)
                    overlay[k] = max(overlay.get(k, 0.0), w)

        if not has_per_key(engine):
            global_w = max(overlay.values(), default=0.0)
            rs = sum(c[0] for c in base.values())
            gs = sum(c[1] for c in base.values())
            bs = sum(c[2] for c in base.values())
            n = max(1, len(base))
            avg_base = (int(rs / n), int(gs / n), int(bs / n))
            rgb = mix(avg_base, react_color, t=min(1.0, global_w))
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            color_map[k] = mix(base_rgb, react_color, t=min(1.0, w))

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_reactive_fade(engine: "EffectsEngine") -> None:
    _reactive_loop(engine, mode="fade")


def run_reactive_ripple(engine: "EffectsEngine") -> None:
    _reactive_loop(engine, mode="ripple")


def run_reactive_rainbow(engine: "EffectsEngine") -> None:
    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    if not (getattr(engine, "per_key_colors", None) or None):
        background = (5, 5, 5)
        base = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    devices = try_open_evdev_keyboards()
    synthetic = not devices
    spawn_acc = 0.0
    spawn_interval_s = max(0.10, 0.45 / max(0.1, p))
    keymap = load_active_profile_keymap()

    @dataclass
    class _RainbowPulse:
        row: int
        col: int
        age_s: float
        ttl_s: float
        hue_offset: float

    pulses: List[_RainbowPulse] = []
    global_hue = 0.0

    while engine.running and not engine.stop_event.is_set():
        pressed_key_id = poll_keypress_key_id(devices)
        pressed = bool(pressed_key_id)

        if synthetic:
            spawn_acc += dt
            if spawn_acc >= spawn_interval_s:
                spawn_acc = 0.0
                pressed = True

        if pressed:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            ttl = 0.50 / p
            pulses.append(_RainbowPulse(row=rr, col=cc, age_s=0.0, ttl_s=ttl, hue_offset=global_hue))

        new_pulses: List[_RainbowPulse] = []
        for pulse in pulses:
            pulse.age_s += dt
            if pulse.age_s <= pulse.ttl_s:
                new_pulses.append(pulse)
        pulses = new_pulses

        overlay: Dict[Key, Tuple[float, float]] = {}
        for pulse in pulses:
            intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
            hue = (pulse.hue_offset + (pulse.age_s / pulse.ttl_s) * 360.0) % 360.0
            radius = int(round(1 + 3 * (pulse.age_s / pulse.ttl_s)))
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    r = pulse.row + dr
                    c = pulse.col + dc
                    if r < 0 or r >= NUM_ROWS or c < 0 or c >= NUM_COLS:
                        continue
                    d = abs(dr) + abs(dc)
                    if d > radius:
                        continue
                    w = max(0.0, intensity * (1.0 - (d / max(1.0, float(radius)))))
                    k = (r, c)
                    if k not in overlay or w > overlay[k][0]:
                        overlay[k] = (w, hue)

        if not has_per_key(engine):
            global_w = max((v[0] for v in overlay.values()), default=0.0)
            avg_hue = sum(v[1] for v in overlay.values()) / max(1, len(overlay)) if overlay else 0.0
            rgb = hsv_to_rgb(avg_hue, 1.0, global_w)
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            global_hue = (global_hue + 2.0 * p) % 360.0
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            if k in overlay:
                w, hue = overlay[k]
                pulse_rgb = hsv_to_rgb(hue, 1.0, 1.0)
                color_map[k] = mix(base_rgb, pulse_rgb, t=min(1.0, w))
            else:
                color_map[k] = base_rgb

        render(engine, color_map=color_map)
        global_hue = (global_hue + 2.0 * p) % 360.0
        engine.stop_event.wait(dt)


def run_reactive_snake(engine: "EffectsEngine") -> None:
    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    react_color_src = getattr(engine, "current_color", None) or (0, 255, 255)
    react_color = (int(react_color_src[0]), int(react_color_src[1]), int(react_color_src[2]))

    if not (getattr(engine, "per_key_colors", None) or None):
        background = scale(react_color, 0.08)
        base = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    devices = try_open_evdev_keyboards()
    synthetic = not devices
    spawn_acc = 0.0
    spawn_interval_s = max(0.10, 0.45 / max(0.1, p))
    keymap = load_active_profile_keymap()

    @dataclass
    class _SnakeSegment:
        row: int
        col: int
        age_s: float

    trail: List[_SnakeSegment] = []
    max_trail_len = 12
    segment_ttl_s = 1.2 / p

    while engine.running and not engine.stop_event.is_set():
        pressed_key_id = poll_keypress_key_id(devices)
        pressed = bool(pressed_key_id)

        if synthetic:
            spawn_acc += dt
            if spawn_acc >= spawn_interval_s:
                spawn_acc = 0.0
                pressed = True

        if pressed:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            trail.append(_SnakeSegment(row=rr, col=cc, age_s=0.0))
            if len(trail) > max_trail_len:
                trail.pop(0)

        new_trail: List[_SnakeSegment] = []
        for seg in trail:
            seg.age_s += dt
            if seg.age_s <= segment_ttl_s:
                new_trail.append(seg)
        trail = new_trail

        overlay: Dict[Key, float] = {}
        for idx, seg in enumerate(trail):
            position_factor = (idx + 1) / max(1, len(trail))
            age_factor = 1.0 - (seg.age_s / segment_ttl_s)
            intensity = position_factor * age_factor
            k = (seg.row, seg.col)
            overlay[k] = max(overlay.get(k, 0.0), intensity)

        if not has_per_key(engine):
            global_w = max(overlay.values(), default=0.0)
            rs = sum(c[0] for c in base.values())
            gs = sum(c[1] for c in base.values())
            bs = sum(c[2] for c in base.values())
            n = max(1, len(base))
            avg_base = (int(rs / n), int(gs / n), int(bs / n))
            rgb = mix(avg_base, react_color, t=min(1.0, global_w))
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            color_map[k] = mix(base_rgb, react_color, t=min(1.0, w))

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)
