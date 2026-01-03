from __future__ import annotations

import colorsys
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.transitions import avoid_full_black

from .input import load_active_profile_keymap, poll_keypress_key_id, try_open_evdev_keyboards
from .render import Color, Key, base_color_map, frame_dt_s, has_per_key, mix, pace, render, scale

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def _srgb_channel_to_linear(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: Color) -> float:
    r, g, b = rgb
    rl = _srgb_channel_to_linear(r / 255.0)
    gl = _srgb_channel_to_linear(g / 255.0)
    bl = _srgb_channel_to_linear(b / 255.0)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def _contrast_ratio(a: Color, b: Color) -> float:
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    lighter = max(la, lb)
    darker = min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _pick_contrasting_highlight(*, base_rgb: Color, preferred_rgb: Color) -> Color:
    """Pick a highlight that stays visible over the base.

    We prefer the user's chosen color when it has enough contrast; otherwise fall
    back to a high-contrast alternative.
    """

    # If the preferred highlight already stands out, keep it.
    if _contrast_ratio(base_rgb, preferred_rgb) >= 2.2:
        return preferred_rgb

    inv = (255 - preferred_rgb[0], 255 - preferred_rgb[1], 255 - preferred_rgb[2])
    candidates: List[Color] = [preferred_rgb, inv, (255, 255, 255), (0, 0, 0)]

    best = preferred_rgb
    best_ratio = 0.0
    for c in candidates:
        ratio = _contrast_ratio(base_rgb, c)
        if ratio > best_ratio:
            best_ratio = ratio
            best = c
    return best


def _rgb_to_hsv01(rgb: Color) -> tuple[float, float, float]:
    r, g, b = rgb
    return colorsys.rgb_to_hsv(float(r) / 255.0, float(g) / 255.0, float(b) / 255.0)


def _tone_shift_from_base(*, base_rgb: Color, hue_shift: float = 0.085, sat_boost: float = 0.25, val_boost: float = 0.35) -> Color:
    """Generate a visible pulse color by shifting the base key's tone.

    This is intended for per-key backdrops: the ripple/snake should preserve the
    user's pre-set per-key colors, and just "push" the hue/value a bit as the
    wave passes through.
    """

    h, s, v = _rgb_to_hsv01(base_rgb)
    h = (h + float(hue_shift)) % 1.0
    s = min(1.0, float(s) + float(sat_boost))
    v = min(1.0, float(v) + float(val_boost))
    return hsv_to_rgb(h, s, v)


@dataclass
class _Pulse:
    row: int
    col: int
    age_s: float
    ttl_s: float


def _ripple_weight(*, d: int, radius: float, intensity: float, band: float) -> float:
    """Compute an expanding-ring ripple weight.

    `d` is a Manhattan distance from the pulse center.
    """

    if band <= 0.0:
        return 0.0
    return max(0.0, float(intensity) * (1.0 - (abs(float(d) - float(radius)) / float(band))))


def _ripple_radius(*, age_s: float, ttl_s: float, min_radius: float = 0.0, max_radius: float = 8.0) -> float:
    if ttl_s <= 0.0:
        return float(min_radius)
    t = max(0.0, min(1.0, float(age_s) / float(ttl_s)))
    return float(min_radius + (max_radius - min_radius) * t)


def _reactive_loop(engine: "EffectsEngine", *, mode: str) -> None:
    base = base_color_map(engine)
    dt = frame_dt_s()
    p = pace(engine)

    per_key_backdrop_active = bool(getattr(engine, "per_key_colors", None) or None)

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

            # Prefer an expanding *ring* instead of a filled diamond, otherwise
            # it reads too much like a local fade (especially on per-key
            # backdrops).
            radius_f = _ripple_radius(age_s=pulse.age_s, ttl_s=pulse.ttl_s, min_radius=0.0, max_radius=8.0)
            band = 1.35
            radius_i = int(math.ceil(radius_f + band))

            for dr in range(-radius_i, radius_i + 1):
                for dc in range(-radius_i, radius_i + 1):
                    r = pulse.row + dr
                    c = pulse.col + dc
                    if r < 0 or r >= NUM_ROWS or c < 0 or c >= NUM_COLS:
                        continue
                    d = abs(dr) + abs(dc)
                    if d > radius_i:
                        continue

                    ring_w = _ripple_weight(d=d, radius=radius_f, intensity=intensity, band=band)

                    # Add a small center flash early so the origin key still
                    # reads as the source of the ripple.
                    disk_w = max(0.0, float(intensity) * (1.0 - (float(d) / max(1.0, float(radius_i)))))
                    w = max(ring_w, 0.22 * disk_w)

                    k = (r, c)
                    overlay[k] = max(overlay.get(k, 0.0), w)

        if not has_per_key(engine):
            global_w = max(overlay.values(), default=0.0)
            rs = sum(c[0] for c in base.values())
            gs = sum(c[1] for c in base.values())
            bs = sum(c[2] for c in base.values())
            n = max(1, len(base))
            avg_base = (int(rs / n), int(gs / n), int(bs / n))
            pulse_rgb = _pick_contrasting_highlight(base_rgb=avg_base, preferred_rgb=react_color)
            rgb = mix(avg_base, pulse_rgb, t=min(1.0, global_w))
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            if per_key_backdrop_active and mode in {"ripple", "fade"}:
                pulse_rgb = _tone_shift_from_base(base_rgb=base_rgb)
            else:
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb, preferred_rgb=react_color)
            color_map[k] = mix(base_rgb, pulse_rgb, t=min(1.0, w))

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

    per_key_backdrop_active = bool(getattr(engine, "per_key_colors", None) or None)

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

    # A continuously moving snake that resets to the pressed key (reactive).
    max_len = 12
    tail: deque[Key] = deque(maxlen=max_len)

    head_idx = random.randrange(NUM_ROWS * NUM_COLS)
    move_acc = 0.0
    move_interval_s = max(0.02, 0.12 / max(0.1, p))

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
                rr = max(0, min(NUM_ROWS - 1, rr))
                cc = max(0, min(NUM_COLS - 1, cc))
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            head_idx = rr * NUM_COLS + cc
            tail.clear()

        move_acc += dt
        while move_acc >= move_interval_s:
            move_acc -= move_interval_s
            head_idx = (head_idx + 1) % (NUM_ROWS * NUM_COLS)
            rr = head_idx // NUM_COLS
            cc = head_idx % NUM_COLS
            tail.append((rr, cc))

        overlay: Dict[Key, float] = {}
        if tail:
            n = len(tail)
            for i, k in enumerate(tail):
                # Head is the newest element (right side) -> brightest.
                position_factor = float(i + 1) / float(n)
                overlay[k] = max(overlay.get(k, 0.0), position_factor)

        if not has_per_key(engine):
            global_w = max(overlay.values(), default=0.0)
            rs = sum(c[0] for c in base.values())
            gs = sum(c[1] for c in base.values())
            bs = sum(c[2] for c in base.values())
            n = max(1, len(base))
            avg_base = (int(rs / n), int(gs / n), int(bs / n))
            pulse_rgb = _pick_contrasting_highlight(base_rgb=avg_base, preferred_rgb=react_color)
            rgb = mix(avg_base, pulse_rgb, t=min(1.0, global_w))
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            if per_key_backdrop_active:
                pulse_rgb = _tone_shift_from_base(base_rgb=base_rgb)
            else:
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb, preferred_rgb=react_color)
            color_map[k] = mix(base_rgb, pulse_rgb, t=min(1.0, w))

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)
