from __future__ import annotations

import math
from collections.abc import Sequence

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.reactive.utils import (
    _pick_contrasting_highlight,
    _Pulse,
    _RainbowPulse,
    _ripple_radius,
    _ripple_weight,
    pulse_decay_ease_out,
)

from .render import Color, Key, mix, scale


def get_engine_overlay_buffer(engine: object, attr_name: str):
    try:
        engine_state = object.__getattribute__(engine, "__dict__")
    except (AttributeError, TypeError):
        engine_state = None

    if isinstance(engine_state, dict):
        existing = engine_state.get(attr_name)
        if isinstance(existing, dict):
            return existing

        created: dict = {}
        engine_state[attr_name] = created
        return created

    created: dict = {}  # type: ignore[no-redef]
    try:
        setattr(engine, attr_name, created)
    except (AttributeError, TypeError):
        return created
    return created


def build_fade_overlay_into(dest: dict[Key, float], pulses: Sequence[_Pulse]) -> dict[Key, float]:
    dest.clear()
    for pulse in pulses:
        intensity = pulse_decay_ease_out(age_s=pulse.age_s, ttl_s=pulse.ttl_s)
        key = (pulse.row, pulse.col)
        dest[key] = max(dest.get(key, 0.0), intensity)
    return dest


# Decay window stretch factor. The ring reaches the farthest key exactly at
# age=ttl (radius is normalized per-pulse, see below); decaying against a
# slightly longer window keeps the far-edge "touchdown" at ~7% intensity
# instead of zero, so the wave visibly lands at the deck edge rather than
# evaporating one step early.
_DECAY_TTL_STRETCH: float = 1.2


def build_ripple_overlay_into(
    dest: dict[Key, tuple[float, float]],
    pulses: list[_RainbowPulse],
    *,
    band: float,
) -> dict[Key, tuple[float, float]]:
    dest.clear()
    for pulse in pulses:
        # Normalize the expansion to this pulse's own farthest in-bounds key
        # (Manhattan). The ring then spends its entire TTL travelling across
        # the deck and arrives at the far corner exactly at end of life,
        # instead of racing to a global max_radius and spending half its life
        # (and most of its brightness) expanding invisibly beyond the edges.
        # Trade-off: wave speed becomes location-dependent (a corner press
        # crosses 25 keys per TTL, a center press ~13), which reads as a
        # consistent full-deck crossing time from anywhere.
        max_d = max(pulse.row, NUM_ROWS - 1 - pulse.row) + max(pulse.col, NUM_COLS - 1 - pulse.col)
        if max_d <= 0:
            continue

        intensity = pulse_decay_ease_out(age_s=pulse.age_s, ttl_s=pulse.ttl_s * _DECAY_TTL_STRETCH)
        if intensity <= 0.0:
            continue
        radius_f = _ripple_radius(
            age_s=pulse.age_s,
            ttl_s=pulse.ttl_s,
            min_radius=0.0,
            max_radius=float(max_d),
        )
        radius_i = math.ceil(radius_f + band)

        # Iterate the Manhattan diamond directly (|dr| + |dc| <= radius_i)
        # instead of scanning the full square and filtering: ~2x fewer cells.
        for dr in range(-radius_i, radius_i + 1):
            r = pulse.row + dr
            if r < 0 or r >= NUM_ROWS:
                continue
            abs_dr = abs(dr)
            for dc in range(abs_dr - radius_i, radius_i - abs_dr + 1):
                c = pulse.col + dc
                if c < 0 or c >= NUM_COLS:
                    continue
                d = abs_dr + abs(dc)

                w = _ripple_weight(d=d, radius=radius_f, intensity=intensity, band=band)
                if w <= 0.0:
                    continue

                hue = (pulse.hue_offset + (float(d) * 18.0) + (pulse.age_s / pulse.ttl_s) * 360.0) % 360.0
                key = (r, c)
                if key not in dest or w > dest[key][0]:
                    dest[key] = (w, hue)

    return dest


def build_ripple_overlay(pulses: list[_RainbowPulse], *, band: float) -> dict[Key, tuple[float, float]]:
    return build_ripple_overlay_into({}, pulses, band=band)


def build_ripple_color_map_into(
    dest: dict[Key, Color],
    *,
    base: dict[Key, Color],
    base_unscaled: dict[Key, Color],
    overlay: dict[Key, tuple[float, float]],
    per_key_backdrop_active: bool,
    manual: Color | None,
    pulse_scale: float,
    auto_pulse_saturation: float = 1.0,
) -> dict[Key, Color]:
    dest.clear()
    saturation = max(0.0, min(1.0, float(auto_pulse_saturation)))
    for key, base_rgb in base.items():
        base_rgb_unscaled = base_unscaled.get(key, base_rgb)
        if key in overlay:
            w, hue = overlay[key]
            if manual is not None:
                pulse_rgb = manual
            else:
                pulse_rgb = hsv_to_rgb(hue / 360.0, saturation, 1.0)
            if per_key_backdrop_active and manual is None:
                pulse_rgb = _pick_contrasting_highlight(base_rgb=base_rgb_unscaled, preferred_rgb=pulse_rgb)
                dest[key] = mix(base_rgb, pulse_rgb, t=min(1.0, w * pulse_scale))
            else:
                if pulse_scale < 0.999:
                    pulse_rgb = scale(pulse_rgb, pulse_scale)
                dest[key] = mix(base_rgb, pulse_rgb, t=min(1.0, w))
        else:
            dest[key] = base_rgb
    return dest


def build_ripple_color_map(
    *,
    base: dict[Key, Color],
    base_unscaled: dict[Key, Color],
    overlay: dict[Key, tuple[float, float]],
    per_key_backdrop_active: bool,
    manual: Color | None,
    pulse_scale: float,
    auto_pulse_saturation: float = 1.0,
) -> dict[Key, Color]:
    return build_ripple_color_map_into(
        {},
        base=base,
        base_unscaled=base_unscaled,
        overlay=overlay,
        per_key_backdrop_active=per_key_backdrop_active,
        manual=manual,
        pulse_scale=pulse_scale,
        auto_pulse_saturation=auto_pulse_saturation,
    )
