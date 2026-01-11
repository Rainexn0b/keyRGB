from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS

from .input import (
    load_active_profile_keymap,
    poll_keypress_key_id,
    try_open_evdev_keyboards,
)
from .render import (
    Color,
    Key,
    apply_backdrop_brightness_scale,
    backdrop_brightness_scale_factor,
    base_color_map,
    frame_dt_s,
    mix,
    pace,
    pulse_brightness_scale_factor,
    render,
    scale,
)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def _get_engine_manual_reactive_color(engine: "EffectsEngine") -> Color | None:
    if not bool(getattr(engine, "reactive_use_manual_color", False)):
        return None
    src = getattr(engine, "reactive_color", None)
    if src is None:
        return None
    try:
        return (int(src[0]), int(src[1]), int(src[2]))
    except Exception:
        return None


def _get_engine_reactive_color(engine: "EffectsEngine") -> Color:
    manual = _get_engine_manual_reactive_color(engine)
    if manual is not None:
        return manual
    src = getattr(engine, "current_color", None) or (255, 255, 255)
    return (int(src[0]), int(src[1]), int(src[2]))


def _build_frame_base_maps(
    engine: "EffectsEngine", *, background_rgb: Color
) -> tuple[bool, Dict[Key, Color], Dict[Key, Color]]:
    per_key_backdrop_active = bool(getattr(engine, "per_key_colors", None) or None)
    if per_key_backdrop_active:
        base_unscaled = base_color_map(engine)
        factor = backdrop_brightness_scale_factor(
            engine, effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0)
        )
        base = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
        return True, base_unscaled, base

    base_unscaled = {(r, c): background_rgb for r in range(NUM_ROWS) for c in range(NUM_COLS)}
    return False, base_unscaled, dict(base_unscaled)


def _age_pulses_in_place(pulses: List[Any], *, dt: float) -> List[Any]:
    new_pulses: List[Any] = []
    for pulse in pulses:
        pulse.age_s += dt
        if pulse.age_s <= pulse.ttl_s:
            new_pulses.append(pulse)
    return new_pulses


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


def _brightness_boost_pulse(*, base_rgb: Color) -> Color:
    """Generate a visible pulse by brightening/whitening the base color.

    This produces a "flash" effect that's visible on ANY base color by:
    1. Significantly boosting brightness
    2. Reducing saturation to add white

    This is more universally visible than hue shifting, which can produce
    similar-looking colors for some base colors (e.g., cyan -> blue).
    """
    h, s, v = _rgb_to_hsv01(base_rgb)

    # Reduce saturation to add white/pastel effect (makes pulse lighter)
    # Boost value to maximum for bright flash
    s = max(0.0, float(s) * 0.3)  # Reduce saturation significantly
    v = 1.0  # Maximum brightness

    return hsv_to_rgb(h, s, v)


@dataclass
class _Pulse:
    row: int
    col: int
    age_s: float
    ttl_s: float


@dataclass
class _RainbowPulse:
    row: int
    col: int
    age_s: float
    ttl_s: float
    hue_offset: float


@dataclass
class _PressSource:
    devices: list
    synthetic: bool
    spawn_interval_s: float
    spawn_acc: float = 0.0

    def poll_key_id(self, *, dt: float) -> str | None:
        """Return a key id (string) when pressed.

        For synthetic mode (no evdev devices), returns an empty string "" when
        a synthetic press should be spawned, and None otherwise.
        """

        key_id = poll_keypress_key_id(self.devices)
        if key_id:
            return str(key_id)

        if self.synthetic:
            self.spawn_acc += float(dt)
            if self.spawn_acc >= float(self.spawn_interval_s):
                self.spawn_acc = 0.0
                return ""

        return None


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


def _reactive_fade_loop(engine: "EffectsEngine") -> None:
    dt = frame_dt_s()
    p = pace(engine)

    devices = try_open_evdev_keyboards() or []
    press = _PressSource(
        devices=devices,
        synthetic=not bool(devices),
        spawn_interval_s=max(0.10, 0.45 / max(0.1, p)),
    )

    keymap = load_active_profile_keymap()

    pulses: List[_Pulse] = []
    while engine.running and not engine.stop_event.is_set():
        try:
            eff_hw = int(getattr(engine, "reactive_brightness", 0) or 0)
        except Exception:
            eff_hw = 0

        react_color = _get_engine_reactive_color(engine)
        manual = _get_engine_manual_reactive_color(engine)

        pressed_key_id = press.poll_key_id(dt=dt)
        if pressed_key_id is not None:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            # Slightly longer lifetime so the ripple travels further.
            ttl = 0.48 / p
            pulses.append(_Pulse(row=rr, col=cc, age_s=0.0, ttl_s=ttl))

        pulses = _age_pulses_in_place(pulses, dt=dt)

        overlay: Dict[Key, float] = {}
        for pulse in pulses:
            intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
            overlay[(pulse.row, pulse.col)] = max(overlay.get((pulse.row, pulse.col), 0.0), intensity)

        per_key_backdrop_active, base_unscaled, base = _build_frame_base_maps(
            engine, background_rgb=scale(react_color, 0.06)
        )

        # When reactive brightness is 0, treat reactive typing as disabled.
        # Keep the current background/backdrop rendering but suppress pulses.
        if eff_hw <= 0:
            render(engine, color_map=base)
            engine.stop_event.wait(dt)
            continue

        pulse_scale = pulse_brightness_scale_factor(engine)

        # Uniform-only backends cannot display per-key pulses; averaging a full
        # keyboard map dilutes highlights too much to be visibly animated.
        # Render a representative mixed color instead.
        if not bool(getattr(engine.kb, "set_key_colors", None)):
            w_global = 0.0
            if overlay:
                try:
                    w_global = max(float(v) for v in overlay.values())
                except Exception:
                    w_global = 0.0

            # Pick representative base colors.
            try:
                base_rgb = next(iter(base.values()))
            except Exception:
                base_rgb = (0, 0, 0)
            try:
                base_rgb_unscaled = next(iter(base_unscaled.values()))
            except Exception:
                base_rgb_unscaled = base_rgb

            if manual is not None:
                pulse_rgb = react_color
            elif per_key_backdrop_active:
                pulse_rgb = _brightness_boost_pulse(base_rgb=base_rgb_unscaled)
            else:
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=react_color)

            if pulse_scale < 0.999:
                pulse_rgb = scale(pulse_rgb, pulse_scale)

            rgb = mix(base_rgb, pulse_rgb, t=min(1.0, w_global))
            render(engine, color_map={(0, 0): rgb})
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            base_rgb_unscaled = base_unscaled.get(k, base_rgb)
            w = overlay.get(k, 0.0)
            if manual is not None:
                pulse_rgb = react_color
            elif per_key_backdrop_active:
                # Use brightness boost for visible flash on any color
                pulse_rgb = _brightness_boost_pulse(base_rgb=base_rgb_unscaled)
            else:
                # Use contrasting highlight for uniform backgrounds
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=react_color)

            if pulse_scale < 0.999:
                pulse_rgb = scale(pulse_rgb, pulse_scale)

            color_map[k] = mix(base_rgb, pulse_rgb, t=min(1.0, w))

        render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_reactive_fade(engine: "EffectsEngine") -> None:
    _reactive_fade_loop(engine)


def run_reactive_ripple(engine: "EffectsEngine") -> None:
    # Ripple implementation: an expanding ring wave that reads clearly across
    # the keyboard.
    dt = frame_dt_s()
    p = pace(engine)

    def _build_overlay(pulses: List[_RainbowPulse], *, band: float) -> Dict[Key, Tuple[float, float]]:
        overlay: Dict[Key, Tuple[float, float]] = {}
        max_radius = float((NUM_ROWS - 1) + (NUM_COLS - 1))
        for pulse in pulses:
            intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
            radius_f = _ripple_radius(
                age_s=pulse.age_s,
                ttl_s=pulse.ttl_s,
                min_radius=0.0,
                max_radius=max_radius,
            )
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

                    w = _ripple_weight(d=d, radius=radius_f, intensity=intensity, band=band)
                    if w <= 0.0:
                        continue

                    hue = (pulse.hue_offset + (float(d) * 18.0) + (pulse.age_s / pulse.ttl_s) * 360.0) % 360.0
                    k = (r, c)
                    if k not in overlay or w > overlay[k][0]:
                        overlay[k] = (w, hue)

        return overlay

    def _build_color_map(
        *,
        base: Dict[Key, Color],
        base_unscaled: Dict[Key, Color],
        overlay: Dict[Key, Tuple[float, float]],
        per_key_backdrop_active: bool,
        manual: Color | None,
        pulse_scale: float,
    ) -> Dict[Key, Color]:
        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            base_rgb_unscaled = base_unscaled.get(k, base_rgb)
            if k in overlay:
                w, hue = overlay[k]
                if manual is not None:
                    pulse_rgb = manual
                else:
                    pulse_rgb = hsv_to_rgb(hue / 360.0, 1.0, 1.0)
                if per_key_backdrop_active and manual is None:
                    pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=pulse_rgb)

                if pulse_scale < 0.999:
                    pulse_rgb = scale(pulse_rgb, pulse_scale)

                color_map[k] = mix(base_rgb, pulse_rgb, t=min(1.0, w))
            else:
                color_map[k] = base_rgb
        return color_map

    # Base map is built per-frame so changes to per-key backdrop/brightness
    # are reflected immediately.

    devices = try_open_evdev_keyboards() or []
    press = _PressSource(
        devices=devices,
        synthetic=not bool(devices),
        spawn_interval_s=max(0.10, 0.45 / max(0.1, p)),
    )
    keymap = load_active_profile_keymap()

    pulses: List[_RainbowPulse] = []
    global_hue = 0.0

    while engine.running and not engine.stop_event.is_set():
        try:
            eff_hw = int(getattr(engine, "reactive_brightness", 0) or 0)
        except Exception:
            eff_hw = 0

        per_key_backdrop_active, base_unscaled, base = _build_frame_base_maps(engine, background_rgb=(5, 5, 5))

        if eff_hw <= 0:
            render(engine, color_map=base)
            engine.stop_event.wait(dt)
            continue

        pressed_key_id = press.poll_key_id(dt=dt)
        if pressed_key_id is not None:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            ttl = 0.65 / p
            pulses.append(_RainbowPulse(row=rr, col=cc, age_s=0.0, ttl_s=ttl, hue_offset=global_hue))

        pulses = _age_pulses_in_place(pulses, dt=dt)

        band = 2.15
        overlay = _build_overlay(pulses, band=band)

        manual = _get_engine_manual_reactive_color(engine)
        pulse_scale = pulse_brightness_scale_factor(engine)

        if not bool(getattr(engine.kb, "set_key_colors", None)):
            best_w = 0.0
            best_hue = 0.0
            for _k, (w, hue) in overlay.items():
                if float(w) > float(best_w):
                    best_w = float(w)
                    best_hue = float(hue)

            # Representative base color (average backdrop if present).
            if base:
                rs = sum(c[0] for c in base.values())
                gs = sum(c[1] for c in base.values())
                bs = sum(c[2] for c in base.values())
                n = max(1, len(base))
                base_rgb = (int(rs / n), int(gs / n), int(bs / n))
            else:
                base_rgb = (0, 0, 0)

            if manual is not None:
                pulse_rgb = manual
            else:
                pulse_rgb = hsv_to_rgb(best_hue / 360.0, 1.0, 1.0)

            if pulse_scale < 0.999:
                pulse_rgb = scale(pulse_rgb, pulse_scale)

            rgb = mix(base_rgb, pulse_rgb, t=min(1.0, best_w))
            render(engine, color_map={(0, 0): rgb})
            global_hue = (global_hue + 2.0 * p) % 360.0
            engine.stop_event.wait(dt)
            continue

        color_map = _build_color_map(
            base=base,
            base_unscaled=base_unscaled,
            overlay=overlay,
            per_key_backdrop_active=per_key_backdrop_active,
            manual=manual,
            pulse_scale=pulse_scale,
        )

        render(engine, color_map=color_map)
        global_hue = (global_hue + 2.0 * p) % 360.0
        engine.stop_event.wait(dt)
