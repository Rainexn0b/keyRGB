from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.reactive.utils import (
    _Pulse,
    _RainbowPulse,
    _PressSource,
    _age_pulses_in_place,
    _brightness_boost_pulse,
    _pick_contrasting_highlight,
    _ripple_radius,
    _ripple_weight,
)
from ._base_maps import (
    build_frame_base_maps,
    get_engine_color_map_buffer,
)
from ._ripple_helpers import (
    build_fade_overlay_into,
    build_ripple_color_map_into,
    build_ripple_overlay_into,
    get_engine_overlay_buffer,
)
from .input import (
    load_active_profile_keymap,
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


def _set_reactive_active_pulse_mix(engine: "EffectsEngine", *, target: float) -> None:
    """Update the live reactive pulse mix with a short tail decay.

    Ripple/fade overlays can disappear abruptly when the last pulse ages out,
    which would drop the entire keyboard from lifted hardware brightness back to
    idle in one frame.  Preserve a tiny decay tail so the end of the effect is
    less perceptible keyboard-wide.
    """

    try:
        prev = float(getattr(engine, "_reactive_active_pulse_mix", 0.0) or 0.0)
    except Exception:
        prev = 0.0

    target_f = max(0.0, min(1.0, float(target)))
    if target_f <= 0.0 and prev > 0.0:
        next_mix = max(0.0, prev - 0.34)
    else:
        next_mix = target_f

    try:
        engine._reactive_active_pulse_mix = float(next_mix)
    except Exception:
        pass


def _render_uniform_fallback(engine: "EffectsEngine", *, rgb: Color) -> None:
    color_map = get_engine_color_map_buffer(engine, "_reactive_uniform_fallback_map")
    color_map.clear()
    color_map[(0, 0)] = rgb
    render(engine, color_map=color_map)


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

        overlay = get_engine_overlay_buffer(engine, "_reactive_fade_overlay")
        build_fade_overlay_into(overlay, pulses)

        try:
            target_mix = max((float(v) for v in overlay.values()), default=0.0)
        except Exception:
            target_mix = 0.0
        _set_reactive_active_pulse_mix(engine, target=target_mix)

        per_key_backdrop_active, base_unscaled, base = build_frame_base_maps(
            engine,
            background_rgb=scale(react_color, 0.06),
            effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0),
            backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
        )

        # When reactive brightness is 0, treat reactive typing as disabled.
        # Keep the current background/backdrop rendering but suppress pulses.
        if eff_hw <= 0:
            _set_reactive_active_pulse_mix(engine, target=0.0)
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
            _render_uniform_fallback(engine, rgb=rgb)
            engine.stop_event.wait(dt)
            continue

        color_map = get_engine_color_map_buffer(engine, "_reactive_fade_frame_map")
        color_map.clear()
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

        per_key_backdrop_active, base_unscaled, base = build_frame_base_maps(
            engine,
            background_rgb=(5, 5, 5),
            effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0),
            backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
        )

        if eff_hw <= 0:
            _set_reactive_active_pulse_mix(engine, target=0.0)
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
        overlay = get_engine_overlay_buffer(engine, "_reactive_ripple_overlay")
        build_ripple_overlay_into(overlay, pulses, band=band)

        try:
            target_mix = max((float(w) for (w, _hue) in overlay.values()), default=0.0)
        except Exception:
            target_mix = 0.0
        _set_reactive_active_pulse_mix(engine, target=target_mix)

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
            _render_uniform_fallback(engine, rgb=rgb)
            global_hue = (global_hue + 2.0 * p) % 360.0
            engine.stop_event.wait(dt)
            continue

        color_map = get_engine_color_map_buffer(engine, "_reactive_ripple_frame_map")
        build_ripple_color_map_into(
            color_map,
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
