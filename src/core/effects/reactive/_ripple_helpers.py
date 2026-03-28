from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.reactive.utils import (
    _Pulse,
    _RainbowPulse,
    _pick_contrasting_highlight,
    _ripple_radius,
    _ripple_weight,
)

from .render import Color, Key, mix, scale


def get_engine_overlay_buffer(engine: object, attr_name: str):
    try:
        existing = getattr(engine, attr_name, None)
    except Exception:
        existing = None

    if isinstance(existing, dict):
        return existing

    created: dict = {}
    try:
        setattr(engine, attr_name, created)
    except Exception:
        pass
    return created


def build_fade_overlay_into(dest: Dict[Key, float], pulses: Sequence[_Pulse]) -> Dict[Key, float]:
    dest.clear()
    for pulse in pulses:
        intensity = 1.0 - (pulse.age_s / pulse.ttl_s)
        key = (pulse.row, pulse.col)
        dest[key] = max(dest.get(key, 0.0), intensity)
    return dest


def build_ripple_overlay_into(
    dest: Dict[Key, Tuple[float, float]],
    pulses: List[_RainbowPulse],
    *,
    band: float,
) -> Dict[Key, Tuple[float, float]]:
    dest.clear()
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
                key = (r, c)
                if key not in dest or w > dest[key][0]:
                    dest[key] = (w, hue)

    return dest


def build_ripple_overlay(pulses: List[_RainbowPulse], *, band: float) -> Dict[Key, Tuple[float, float]]:
    return build_ripple_overlay_into({}, pulses, band=band)


def build_ripple_color_map_into(
    dest: Dict[Key, Color],
    *,
    base: Dict[Key, Color],
    base_unscaled: Dict[Key, Color],
    overlay: Dict[Key, Tuple[float, float]],
    per_key_backdrop_active: bool,
    manual: Color | None,
    pulse_scale: float,
) -> Dict[Key, Color]:
    dest.clear()
    for key, base_rgb in base.items():
        base_rgb_unscaled = base_unscaled.get(key, base_rgb)
        if key in overlay:
            w, hue = overlay[key]
            if manual is not None:
                pulse_rgb = manual
            else:
                pulse_rgb = hsv_to_rgb(hue / 360.0, 1.0, 1.0)
            if per_key_backdrop_active and manual is None:
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=pulse_rgb)

            if pulse_scale < 0.999:
                pulse_rgb = scale(pulse_rgb, pulse_scale)

            dest[key] = mix(base_rgb, pulse_rgb, t=min(1.0, w))
        else:
            dest[key] = base_rgb
    return dest


def build_ripple_color_map(
    *,
    base: Dict[Key, Color],
    base_unscaled: Dict[Key, Color],
    overlay: Dict[Key, Tuple[float, float]],
    per_key_backdrop_active: bool,
    manual: Color | None,
    pulse_scale: float,
) -> Dict[Key, Color]:
    return build_ripple_color_map_into(
        {},
        base=base,
        base_unscaled=base_unscaled,
        overlay=overlay,
        per_key_backdrop_active=per_key_backdrop_active,
        manual=manual,
        pulse_scale=pulse_scale,
    )