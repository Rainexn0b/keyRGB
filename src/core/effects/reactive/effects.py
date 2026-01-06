from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS

from .input import load_active_profile_keymap, poll_keypress_key_id, try_open_evdev_keyboards
from .render import (
    Color,
    Key,
    apply_backdrop_brightness_scale,
    backdrop_brightness_scale_factor,
    base_color_map,
    frame_dt_s,
    mix,
    pace,
    render,
    scale,
)

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

    def _get_reactive_color() -> Color:
        # When manual mode is enabled, prefer the configured reactive_color.
        if bool(getattr(engine, "reactive_use_manual_color", False)):
            src = getattr(engine, "reactive_color", None)
            if src is not None:
                try:
                    return (int(src[0]), int(src[1]), int(src[2]))
                except Exception:
                    pass
        src = getattr(engine, "current_color", None) or (255, 255, 255)
        return (int(src[0]), int(src[1]), int(src[2]))

    devices = try_open_evdev_keyboards()
    press = _PressSource(
        devices=devices,
        synthetic=not devices,
        spawn_interval_s=max(0.10, 0.45 / max(0.1, p)),
    )

    keymap = load_active_profile_keymap()

    pulses: List[_Pulse] = []
    while engine.running and not engine.stop_event.is_set():
        per_key_backdrop_active = bool(getattr(engine, "per_key_colors", None) or None)
        react_color = _get_reactive_color()

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

        new_pulses: List[_Pulse] = []
        for pulse in pulses:
            pulse.age_s += dt
            if pulse.age_s <= pulse.ttl_s:
                new_pulses.append(pulse)
        pulses = new_pulses

        overlay: Dict[Key, float] = {}
        for pulse in pulses:
            intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
            overlay[(pulse.row, pulse.col)] = max(overlay.get((pulse.row, pulse.col), 0.0), intensity)

        # Build the base map for this frame.
        # - With per-key backdrop: use existing per-key colors.
        # - Without backdrop: use a very dim background derived from the reactive color.
        if per_key_backdrop_active:
            base_unscaled = base_color_map(engine)
            factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0))
            base = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
        else:
            background = scale(react_color, 0.06)
            base_unscaled = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}
            base = dict(base_unscaled)

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            base_rgb_unscaled = base_unscaled.get(k, base_rgb)
            w = overlay.get(k, 0.0)
            if bool(getattr(engine, "reactive_use_manual_color", False)):
                pulse_rgb = react_color
            elif per_key_backdrop_active:
                # Use brightness boost for visible flash on any color
                pulse_rgb = _brightness_boost_pulse(base_rgb=base_rgb_unscaled)
            else:
                # Use contrasting highlight for uniform backgrounds
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=react_color)
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

    def _get_manual_color() -> Color | None:
        if not bool(getattr(engine, "reactive_use_manual_color", False)):
            return None
        src = getattr(engine, "reactive_color", None)
        if src is None:
            return None
        try:
            return (int(src[0]), int(src[1]), int(src[2]))
        except Exception:
            return None

    # Base map is built per-frame so changes to per-key backdrop/brightness
    # are reflected immediately.

    devices = try_open_evdev_keyboards()
    press = _PressSource(
        devices=devices,
        synthetic=not devices,
        spawn_interval_s=max(0.10, 0.45 / max(0.1, p)),
    )
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
        per_key_backdrop_active = bool(getattr(engine, "per_key_colors", None) or None)
        if per_key_backdrop_active:
            base_unscaled = base_color_map(engine)
            factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0))
            base = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
        else:
            background = (5, 5, 5)
            base_unscaled = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}
            base = dict(base_unscaled)

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

        new_pulses: List[_RainbowPulse] = []
        for pulse in pulses:
            pulse.age_s += dt
            if pulse.age_s <= pulse.ttl_s:
                new_pulses.append(pulse)
        pulses = new_pulses

        overlay: Dict[Key, Tuple[float, float]] = {}
        max_radius = float((NUM_ROWS - 1) + (NUM_COLS - 1))
        band = 2.15
        for pulse in pulses:
            intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
            radius_f = _ripple_radius(age_s=pulse.age_s, ttl_s=pulse.ttl_s, min_radius=0.0, max_radius=max_radius)
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

                    # Expanding ring weight.
                    w = _ripple_weight(d=d, radius=radius_f, intensity=intensity, band=band)
                    if w <= 0.0:
                        continue

                    # Color structure: hue varies by distance and time.
                    hue = (pulse.hue_offset + (float(d) * 18.0) + (pulse.age_s / pulse.ttl_s) * 360.0) % 360.0
                    k = (r, c)
                    if k not in overlay or w > overlay[k][0]:
                        overlay[k] = (w, hue)

        manual = _get_manual_color()

        # Build the color map for this frame
        # render() will handle fallback to uniform if per-key HW isn't available
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
                    # Preserve the rainbow default, but ensure it stays visible
                    # over the current per-key backdrop.
                    pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=pulse_rgb)
                color_map[k] = mix(base_rgb, pulse_rgb, t=min(1.0, w))
            else:
                color_map[k] = base_rgb

        render(engine, color_map=color_map)
        global_hue = (global_hue + 2.0 * p) % 360.0
        engine.stop_event.wait(dt)
